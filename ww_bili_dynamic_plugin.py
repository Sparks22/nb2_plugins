from __future__ import annotations

import asyncio
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from nonebot import get_bots, get_driver, on_message, require
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.log import logger

current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

try:
    from ww_db_helper import db
except ImportError:
    try:
        from .ww_db_helper import db
    except ImportError:
        from src.plugins.ww_db_helper import db

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

driver = get_driver()
_poll_warmup_done = False


def _today_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _format_ts(ts: int | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _extract_uids(text: str) -> list[int]:
    if not text:
        return []
    text = text.strip()
    if text.startswith(("+", "＋")):
        text = text[1:].strip()
    text = text.replace("，", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    uids: list[int] = []
    for p in parts:
        m = re.search(r"\d{1,20}", p)
        if m:
            try:
                uids.append(int(m.group(0)))
            except Exception:
                pass
    seen = set()
    out: list[int] = []
    for uid in uids:
        if uid not in seen:
            out.append(uid)
            seen.add(uid)
    return out


def _http_json(url: str, timeout: int = 15) -> dict:
    cookie = getattr(driver.config, "ww_bili_cookie", None)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
            "Accept-Language": "zh-CN,zh;q=0.9",
            **({"Cookie": str(cookie)} if cookie else {}),
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return json.loads(body.decode("utf-8", errors="ignore"))


def _get_latest_dynamic(uid: int) -> tuple[str | None, str | None, int | None]:
    try:
        url = f"https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid={uid}&offset_dynamic_id=0"
        data = _http_json(url)
        if data.get("code") == 0:
            cards = (data.get("data") or {}).get("cards") or []
            if cards:
                desc = cards[0].get("desc") or {}
                dynamic_id = str(desc.get("dynamic_id_str") or desc.get("dynamic_id") or "").strip()
                ts = desc.get("timestamp")
                profile = (desc.get("user_profile") or {}).get("info") or {}
                uname = profile.get("uname") or None
                return dynamic_id or None, uname, int(ts) if ts is not None else None
    except Exception:
        pass

    try:
        url = f"https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid={uid}"
        data = _http_json(url)
        if data.get("code") != 0:
            return None, None, None
        items = (data.get("data") or {}).get("items") or []
        if not items:
            return None, None, None
        first = items[0]
        dynamic_id = (
            str(((first.get("id_str") or first.get("id")) or "")).strip()
            or str((((first.get("basic") or {}).get("comment_id_str")) or "")).strip()
        )
        modules = first.get("modules") or {}
        author = (modules.get("module_author")) or {}
        pub_ts = author.get("pub_ts")
        author = (((first.get("modules") or {}).get("module_author")) or {})
        uname = author.get("name") or None
        return dynamic_id or None, uname, int(pub_ts) if pub_ts is not None else None
    except Exception:
        return None, None, None


async def _screenshot_dynamic(dynamic_id: str) -> bytes | None:
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None

    url = f"https://m.bilibili.com/dynamic/{dynamic_id}"
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                viewport={"width": 430, "height": 932},
                user_agent="Mozilla/5.0 (Linux; Android 12; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            img = await page.screenshot(type="jpeg", quality=80, full_page=True)
            await browser.close()
            return img
    except Exception as e:
        err = str(e)
        if "Executable doesn't exist" in err:
            logger.info(f"bili 动态截图失败：缺少浏览器内核，请运行 playwright install chromium")
        logger.info(f"bili 动态截图失败 dynamic_id={dynamic_id} err={e}")
        return None


async def _ensure_tables():
    await db.create_table(
        """
        CREATE TABLE IF NOT EXISTS ww_bili_target (
            uid INTEGER PRIMARY KEY,
            uname TEXT,
            last_dynamic_id TEXT,
            updated_at TEXT
        )
        """
    )
    await db.create_table(
        """
        CREATE TABLE IF NOT EXISTS ww_bili_sub (
            uid INTEGER NOT NULL,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            added_by INTEGER,
            created_at TEXT,
            PRIMARY KEY (uid, target_type, target_id)
        )
        """
    )


@driver.on_startup
async def init_tables():
    await _ensure_tables()


async def _upsert_target(uid: int, uname: str | None):
    await db.execute_update(
        "INSERT INTO ww_bili_target (uid, uname, last_dynamic_id, updated_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(uid) DO UPDATE SET uname=COALESCE(excluded.uname, ww_bili_target.uname), updated_at=excluded.updated_at",
        (uid, uname, None, _today_ts()),
    )


async def _set_last_dynamic(uid: int, dynamic_id: str):
    await db.execute_update(
        "UPDATE ww_bili_target SET last_dynamic_id = ?, updated_at = ? WHERE uid = ?",
        (dynamic_id, _today_ts(), uid),
    )


async def _get_targets() -> list[dict]:
    return await db.fetch_all("SELECT uid, uname, last_dynamic_id FROM ww_bili_target ORDER BY uid ASC")


async def _find_targets_by_uname(uname: str) -> list[dict]:
    rows = await db.fetch_all("SELECT uid, uname FROM ww_bili_target WHERE uname = ? ORDER BY uid ASC", (uname,))
    if rows:
        return rows
    return await db.fetch_all(
        "SELECT uid, uname FROM ww_bili_target WHERE uname LIKE ? ORDER BY uid ASC",
        (f"%{uname}%",),
    )


async def _get_subs_by_uid(uid: int) -> list[dict]:
    return await db.fetch_all(
        "SELECT target_type, target_id FROM ww_bili_sub WHERE uid = ?",
        (uid,),
    )


async def _add_sub(uid: int, target_type: str, target_id: int, added_by: int | None):
    await db.execute_update(
        "INSERT OR IGNORE INTO ww_bili_sub (uid, target_type, target_id, added_by, created_at) VALUES (?, ?, ?, ?, ?)",
        (uid, target_type, target_id, added_by, _today_ts()),
    )


async def _delete_target(uid: int):
    await db.execute_update("DELETE FROM ww_bili_sub WHERE uid = ?", (uid,))
    await db.execute_update("DELETE FROM ww_bili_target WHERE uid = ?", (uid,))



def _event_target(event: MessageEvent) -> tuple[str, int] | None:
    group_id = getattr(event, "group_id", None)
    if group_id is not None:
        return "group", int(group_id)
    user_id = getattr(event, "user_id", None)
    if user_id is not None:
        return "private", int(user_id)
    return None


async def _rule_add(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return text.startswith("ww添加目标")


async def _rule_list(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return text == "ww查看目标"


async def _rule_del(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return text.startswith("ww删除目标")


async def _rule_fetch_latest(event: MessageEvent) -> bool:
    text = event.get_plaintext().strip()
    return bool(re.match(r"^ww查看\+.+\+最新$", text))


ww_add_target = on_message(rule=_rule_add, priority=10, block=True)
ww_list_target = on_message(rule=_rule_list, priority=10, block=True)
ww_del_target = on_message(rule=_rule_del, priority=10, block=True)
ww_fetch_latest = on_message(rule=_rule_fetch_latest, priority=10, block=True)


@ww_add_target.handle()
async def handle_add(bot: Bot, event: MessageEvent):
    raw = event.get_plaintext().strip()
    raw = raw.replace("ww添加目标", "", 1).strip()
    uids = _extract_uids(raw)
    if not uids:
        await ww_add_target.finish("用法：ww添加目标+哔哩哔哩UID（多个用英文逗号分隔）")
        return

    tgt = _event_target(event)
    if not tgt:
        await ww_add_target.finish("无法识别当前会话类型")
        return
    target_type, target_id = tgt

    added = 0
    for uid in uids:
        dynamic_id, uname, _ = await asyncio.to_thread(_get_latest_dynamic, uid)
        await _upsert_target(uid, uname)
        if dynamic_id:
            await _set_last_dynamic(uid, dynamic_id)
        await _add_sub(uid, target_type, target_id, getattr(event, "user_id", None))
        added += 1

    await ww_add_target.finish(f"已添加 {added} 个目标")


@ww_list_target.handle()
async def handle_list(bot: Bot, event: MessageEvent):
    targets = await _get_targets()
    if not targets:
        await ww_list_target.finish("当前没有任何正在侦测的哔哩哔哩用户")
        return
    lines = []
    for t in targets:
        uid = t.get("uid")
        uname = t.get("uname") or "未知"
        lines.append(f"{uid} - {uname}")
    await ww_list_target.finish("正在侦测的目标：\n" + "\n".join(lines))


@ww_del_target.handle()
async def handle_del(bot: Bot, event: MessageEvent):
    raw = event.get_plaintext().strip()
    raw = raw.replace("ww删除目标", "", 1).strip()
    uids = _extract_uids(raw)
    if not uids:
        await ww_del_target.finish("用法：ww删除目标+哔哩哔哩UID（多个用英文逗号分隔）")
        return

    removed = 0
    for uid in uids:
        await _delete_target(uid)
        removed += 1
    await ww_del_target.finish(f"已删除 {removed} 个目标")


@ww_fetch_latest.handle()
async def handle_fetch_latest(bot: Bot, event: MessageEvent):
    text = event.get_plaintext().strip()
    m = re.match(r"^ww查看\+(.+)\+最新$", text)
    if not m:
        await ww_fetch_latest.finish("用法：ww查看+用户名+最新")
        return
    uname = m.group(1).strip()
    if not uname:
        await ww_fetch_latest.finish("用法：ww查看+用户名+最新")
        return

    targets = await _find_targets_by_uname(uname)
    if not targets:
        await ww_fetch_latest.finish(f"未添加此目标：{uname}")
        return

    chosen = targets[0]
    if len(targets) > 1:
        lines = [f"{t.get('uid')} - {t.get('uname') or '未知'}" for t in targets[:10]]
        msg = "匹配到多个目标，默认使用第一条：\n" + "\n".join(lines)
        await bot.send(event, msg)

    uid = int(chosen["uid"])
    dynamic_id, latest_uname, pub_ts = await asyncio.to_thread(_get_latest_dynamic, uid)
    if not dynamic_id:
        await ww_fetch_latest.finish(f"获取失败：{chosen.get('uname') or uname}（{uid}）暂无动态或接口不可用")
        return

    pub_time = _format_ts(pub_ts) or "未知时间"
    img = await _screenshot_dynamic(dynamic_id)
    link = f"https://t.bilibili.com/{dynamic_id}"
    title = f"哔哩哔哩最新动态：{latest_uname or chosen.get('uname') or uid}\n🕒 {pub_time}\n{link}"

    if img:
        await ww_fetch_latest.finish(MessageSegment.at(event.user_id) + MessageSegment.image(img) + "\n" + title)
    else:
        await ww_fetch_latest.finish(MessageSegment.at(event.user_id) + "\n" + title)


async def _send_update(uid: int, uname: str | None, dynamic_id: str, pub_time: str | None):
    bots = get_bots()
    if not bots:
        return
    bot: Any = next(iter(bots.values()))

    img = await _screenshot_dynamic(dynamic_id)
    link = f"https://t.bilibili.com/{dynamic_id}"
    pub_line = f"🕒 {pub_time}\n" if pub_time else ""
    title = f"哔哩哔哩新动态：{uname or uid}\n{pub_line}{link}"

    subs = await _get_subs_by_uid(uid)
    for s in subs:
        target_type = s.get("target_type")
        target_id = s.get("target_id")
        try:
            if target_type == "group":
                if img:
                    await bot.send_group_msg(group_id=int(target_id), message=MessageSegment.image(img) + "\n" + title)
                else:
                    await bot.send_group_msg(group_id=int(target_id), message=title)
            else:
                if img:
                    await bot.send_private_msg(user_id=int(target_id), message=MessageSegment.image(img) + "\n" + title)
                else:
                    await bot.send_private_msg(user_id=int(target_id), message=title)
        except Exception as e:
            logger.info(f"bili 动态推送失败 uid={uid} target={target_type}:{target_id} err={e}")


@scheduler.scheduled_job("interval", seconds=90, id="ww_bili_dynamic_poll", max_instances=1)
async def poll_bili_dynamic():
    try:
        global _poll_warmup_done
        await _ensure_tables()
        targets = await _get_targets()
        logger.info(f"bili 动态轮询开始 targets={len(targets)}")
        for t in targets:
            uid = int(t["uid"])
            last_dynamic_id = t.get("last_dynamic_id")
            dynamic_id, uname, pub_ts = await asyncio.to_thread(_get_latest_dynamic, uid)
            if not dynamic_id:
                logger.info(f"bili 动态轮询 uid={uid} 获取失败")
                continue
            if uname:
                await _upsert_target(uid, uname)
            if (not last_dynamic_id) and (not _poll_warmup_done):
                pub_time = _format_ts(pub_ts) or "未知时间"
                logger.info(f"bili 动态热启动记录 uid={uid} dynamic_id={dynamic_id} pub={pub_time}")
                await _set_last_dynamic(uid, dynamic_id)
                continue
            if (last_dynamic_id != dynamic_id) and _poll_warmup_done:
                pub_time = _format_ts(pub_ts) or "未知时间"
                logger.info(f"bili 动态更新 uid={uid} {last_dynamic_id} -> {dynamic_id} pub={pub_time}")
                await _set_last_dynamic(uid, dynamic_id)
                await _send_update(uid, uname, dynamic_id, pub_time)
            else:
                logger.info(f"bili 动态无更新 uid={uid} dynamic_id={dynamic_id}")
        if not _poll_warmup_done:
            _poll_warmup_done = True
            logger.info("bili 动态热启动完成：后续将正常推送新动态")
    except Exception as e:
        logger.info(f"bili 动态轮询失败 err={e}")

