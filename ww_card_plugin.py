from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot import get_driver
from nonebot.log import logger
import json
import sys
from pathlib import Path

# 添加当前文件所在目录到 sys.path，确保能找到同级模块
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

try:
    from wwSrcoe import send_kuro_request
except ImportError:
    # 如果作为包导入失败，尝试相对导入
    try:
        from .wwSrcoe import send_kuro_request
    except ImportError:
        # 最后尝试全路径（假设在 src.plugins 下）
        from src.plugins.wwSrcoe import send_kuro_request

# 导入数据库 helper
try:
    from ww_db_helper import db
except ImportError:
    try:
        from .ww_db_helper import db
    except ImportError:
        from src.plugins.ww_db_helper import db

# 定义常量
API_URL = "https://api.kurobbs.com/aki/roleBox/akiBox/roleData"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJjcmVhdGVkIjoxNzY4NjQ1NjcxNDkxLCJ1c2VySWQiOjIwOTEwNTM1fQ.YD3jbfC02hNPzbrprnPiu1vgKB02eesWbRAChHk6Q64"
METHOD = "POST"

driver = get_driver()

@driver.on_startup
async def init_tables():
    await db.create_table("""
        CREATE TABLE IF NOT EXISTS user_game_role (
            qq_user_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            bind_uid TEXT NOT NULL,
            api_user_id TEXT,
            server_id TEXT,
            server_name TEXT,
            role_id TEXT NOT NULL,
            role_name TEXT,
            role_num INTEGER,
            game_level TEXT,
            role_score TEXT,
            achievement_count INTEGER,
            action_recover_switch INTEGER,
            active_day INTEGER,
            fashion_collection_percent REAL,
            phantom_percent REAL,
            point_after INTEGER,
            game_head_url TEXT,
            head_photo_url TEXT,
            raw_id TEXT,
            is_default INTEGER,
            widget_has_pull INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (qq_user_id, game_id, role_id)
        )
    """)

ww_card_plugin = on_command("ww卡片", priority=10, block=True)

@ww_card_plugin.handle()
async def handle_request(bot: Bot, event: MessageEvent):
    # 强制检查绑定：无论任何情况，都先检查当前用户是否已绑定
    user_id = event.user_id
    row = await db.fetch_one("SELECT game_uid FROM user_bind WHERE user_id = ?", (user_id,))
    
    # 如果未绑定，直接拦截并提示
    if not row:
        await ww_card_plugin.finish("您尚未绑定游戏UID，无法查询卡片。\n请先发送 '绑定+UID' 进行绑定，例如：绑定100123456")
        return

    game_id = 3
    game_name = "鸣潮"

    role_row = await db.fetch_one(
        "SELECT role_id, server_id FROM user_game_role "
        "WHERE qq_user_id = ? AND game_id = ? "
        "ORDER BY is_default DESC, updated_at DESC LIMIT 1",
        (user_id, game_id),
    )
    if not role_row:
        await ww_card_plugin.finish("未找到您的鸣潮角色信息，请先使用“ww查看”同步角色数据后再试")
        return

    # 构造请求数据
    api_data = f"gameId={game_id}&roleId={role_row.get('role_id')}&serverId={role_row.get('server_id')}"

    try:
        # 调用封装好的工具方法
        resp = await send_kuro_request(API_URL, METHOD, TOKEN, api_data)
        
        # 尝试解析 JSON
        try:
            outer = resp.json()
        except json.JSONDecodeError:
            await ww_card_plugin.finish(f"查询失败：返回数据不是有效的 JSON\n{resp.text}")
            return

        if not outer.get("success"):
            await ww_card_plugin.finish(f"查询失败：{outer.get('msg', '未知错误')}")
            return

        inner_raw = outer.get("data")
        try:
            inner = json.loads(inner_raw) if isinstance(inner_raw, str) else (inner_raw or {})
        except Exception:
            await ww_card_plugin.finish("查询失败：返回 data 字段不是有效的 JSON 字符串")
            return

        img_bytes = generate_role_data_image(inner, game_name)
        
        if img_bytes:
             # 回复图片
             await ww_card_plugin.finish(MessageSegment.at(event.user_id) + MessageSegment.image(img_bytes))
        else:
             await ww_card_plugin.finish(f"未找到相关 {game_name} 角色信息或生成图片失败")
            
    except Exception as e:
        logger.info(f"请求发生错误: {str(e)}")
        pass

import io
from PIL import Image, ImageDraw, ImageFont

def generate_role_data_image(data: dict, game_name: str) -> bytes:
    try:
        font_title = ImageFont.truetype("msyhbd.ttc", 36)
        font_content = ImageFont.truetype("msyh.ttc", 22)
        font_small = ImageFont.truetype("msyh.ttc", 18)
    except:
        try:
            font_title = ImageFont.truetype("NotoSansCJK-Bold.ttc", 36)
            font_content = ImageFont.truetype("NotoSansCJK-Regular.ttc", 22)
            font_small = ImageFont.truetype("NotoSansCJK-Regular.ttc", 18)
        except:
            font_title = ImageFont.load_default()
            font_content = ImageFont.load_default()
            font_small = ImageFont.load_default()

    roles = data.get("roleList") or []
    if not isinstance(roles, list) or not roles:
        return None

    width = 860
    row_h = 34
    header_h = 110
    max_roles = 18
    roles_view = roles[:max_roles]
    height = header_h + len(roles_view) * row_h + 30

    bg_color = (240, 248, 255)
    text_color = (0, 0, 0)
    accent_color = (0, 191, 255)

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    title = f"{game_name} 阵容信息"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    text_w = bbox[2] - bbox[0]
    draw.text(((width - text_w) / 2, 24), title, font=font_title, fill=text_color)

    sub = f"角色数: {len(roles)}"
    draw.text((40, 78), sub, font=font_small, fill=text_color)

    y = header_h
    for idx, r in enumerate(roles_view, start=1):
        role_name = r.get("roleName") or "未知"
        level = r.get("level")
        star = r.get("starLevel")
        breach = r.get("breach")
        chain = r.get("chainUnlockNum")
        attr = r.get("attributeName") or ""
        weapon = r.get("weaponTypeName") or ""
        is_main = r.get("isMainRole")

        left = f"{idx:02d}. {'[主] ' if is_main else ''}{role_name}"
        mid = f"Lv.{level if level is not None else '?'}  ★{star if star is not None else '?'}  突破:{breach if breach is not None else '?'}  命座:{chain if chain is not None else '?'}"
        right = f"{attr} / {weapon}".strip(" /")

        draw.text((40, y), left, font=font_content, fill=accent_color if is_main else text_color)
        draw.text((320, y), mid, font=font_small, fill=text_color)
        draw.text((720, y), right, font=font_small, fill=text_color)
        y += row_h

    # 转换为 bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()
