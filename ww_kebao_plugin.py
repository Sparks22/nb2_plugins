from __future__ import annotations

import asyncio
import re
import urllib.request
from urllib.parse import urljoin

from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.log import logger


def _http_get(url: str, timeout: int = 15) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status = int(getattr(resp, "status", 200))
        content_type = resp.headers.get("Content-Type", "") or ""
        content = resp.read()
    return status, content_type, content


def _extract_image_url(html: str, base_url: str) -> str | None:
    patterns = [
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+name=["\']twitter:image["\']\s+content=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            return urljoin(base_url, m.group(1).strip())
    return None


async def _fetch_kebao_image(url: str) -> bytes | None:
    status, content_type, content = await asyncio.to_thread(_http_get, url, 15)
    if status != 200:
        return None
    if "image" in content_type.lower():
        return content

    html = content.decode("utf-8", errors="ignore")
    image_url = _extract_image_url(html, url)
    if not image_url:
        return None

    status2, content_type2, content2 = await asyncio.to_thread(_http_get, image_url, 15)
    if status2 != 200:
        return None
    if "image" not in content_type2.lower():
        return None
    return content2


try:
    ww_kebao_plugin = on_command("ww珂宝", priority=10, block=True)
except Exception:
    ww_kebao_plugin = None
else:

    @ww_kebao_plugin.handle()
    async def handle_kebao(bot: Bot, event: MessageEvent):
        url = "https://i.100295.xyz/"
        try:
            img = await _fetch_kebao_image(url)
            if not img:
                await ww_kebao_plugin.finish("获取图片失败：未能解析到图片")
                return
            await ww_kebao_plugin.finish(MessageSegment.at(event.user_id) + MessageSegment.image(img))
        except Exception as e:
            logger.info(f"ww珂宝请求失败: {e}")
            # await ww_kebao_plugin.finish("获取图片失败：请求异常")


if __name__ == "__main__":
    status, content_type, content = _http_get("https://i.100295.xyz/", 15)
    print("status", status)
    print("content-type", content_type)
    print("len", len(content))
