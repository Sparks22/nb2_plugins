from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment
from nonebot.typing import T_State
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
API_URL = "https://api.kurobbs.com/user/role/findUserDefaultRole"
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

ww_query_plugin = on_command("ww查看", priority=10, block=True)

@ww_query_plugin.handle()
async def handle_request(bot: Bot, event: MessageEvent, state: T_State):
    # 强制检查绑定：无论是否输入了 ID，都先检查当前用户是否已绑定
    user_id = event.user_id
    row = await db.fetch_one("SELECT game_uid FROM user_bind WHERE user_id = ?", (user_id,))
    
    # 如果未绑定，直接拦截并提示
    if not row:
        await ww_query_plugin.finish("您尚未绑定游戏UID，无法使用此功能。\n请先发送 '绑定+UID' 进行绑定，例如：绑定100123456")
        return

    query_user_id = row["game_uid"]

    # 构造请求数据
    api_data = {
        "queryUserId": query_user_id
    }

    try:
        # 调用封装好的工具方法
        resp = await send_kuro_request(API_URL, METHOD, TOKEN, api_data)
        
        # 尝试解析 JSON
        try:
            data = resp.json()
        except json.JSONDecodeError:
            await ww_query_plugin.finish(f"查询失败：返回数据不是有效的 JSON\n{resp.text}")
            return

        # 解析并格式化结果
        result_msg = parse_role_data(data, query_user_id)

        try:
            role_list = data.get("data", {}).get("defaultRoleList", [])
            mingchao_roles = [r for r in role_list if r.get("gameId") == 3]
            for r in mingchao_roles:
                await db.execute_update(
                    "INSERT INTO user_game_role ("
                    "qq_user_id, game_id, bind_uid, api_user_id, server_id, server_name, role_id, role_name, role_num, "
                    "game_level, role_score, achievement_count, action_recover_switch, active_day, fashion_collection_percent, "
                    "phantom_percent, point_after, game_head_url, head_photo_url, raw_id, is_default, widget_has_pull"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(qq_user_id, game_id, role_id) DO UPDATE SET "
                    "bind_uid=excluded.bind_uid, api_user_id=excluded.api_user_id, server_id=excluded.server_id, server_name=excluded.server_name, "
                    "role_name=excluded.role_name, role_num=excluded.role_num, game_level=excluded.game_level, role_score=excluded.role_score, "
                    "achievement_count=excluded.achievement_count, action_recover_switch=excluded.action_recover_switch, active_day=excluded.active_day, "
                    "fashion_collection_percent=excluded.fashion_collection_percent, phantom_percent=excluded.phantom_percent, point_after=excluded.point_after, "
                    "game_head_url=excluded.game_head_url, head_photo_url=excluded.head_photo_url, raw_id=excluded.raw_id, "
                    "is_default=excluded.is_default, widget_has_pull=excluded.widget_has_pull, updated_at=CURRENT_TIMESTAMP",
                    (
                        user_id,
                        3,
                        query_user_id,
                        str(r.get("userId")) if r.get("userId") is not None else None,
                        str(r.get("serverId")) if r.get("serverId") is not None else None,
                        r.get("serverName"),
                        str(r.get("roleId")) if r.get("roleId") is not None else "",
                        r.get("roleName"),
                        r.get("roleNum"),
                        r.get("gameLevel"),
                        r.get("roleScore"),
                        r.get("achievementCount"),
                        1 if r.get("actionRecoverSwitch") else 0 if r.get("actionRecoverSwitch") is not None else None,
                        r.get("activeDay"),
                        r.get("fashionCollectionPercent"),
                        r.get("phantomPercent"),
                        r.get("pointAfter"),
                        r.get("gameHeadUrl"),
                        r.get("headPhotoUrl"),
                        r.get("id"),
                        1 if r.get("isDefault") else 0 if r.get("isDefault") is not None else None,
                        1 if r.get("widgetHasPull") else 0 if r.get("widgetHasPull") is not None else None,
                    ),
                )
        except Exception as e:
            logger.warning(f"保存鸣潮角色数据失败: {e}")

        # 回复用户
        await ww_query_plugin.finish(MessageSegment.at(event.user_id) + result_msg)
            
    except Exception as e:
        logger.info(f"查询失败: {str(e)}")
        pass

def parse_role_data(data: dict, query_id: str) -> str:
    """
    将 API 返回的 JSON 数据解析为用户可读的文本
    """
    if not data.get("success"):
        msg = data.get("msg", "未知错误")
        return f"\n查询ID: {query_id}\n查询失败: {msg}"
    
    # 获取 data 下的 defaultRoleList 列表
    role_list = data.get("data", {}).get("defaultRoleList", [])
    
    if not role_list:
        return f"\n查询ID: {query_id}\n该用户未绑定任何游戏角色"

    result = [f"\n====== 查询结果 (ID: {query_id}) ======"]
    
    for role in role_list:
        # 提取字段
        game_name = "战双帕弥什" if role.get("gameId") == 2 else "鸣潮" if role.get("gameId") == 3 else f"未知游戏({role.get('gameId')})"
        role_name = role.get("roleName", "未知")
        role_id = role.get("roleId", "未知")
        server_name = role.get("serverName", "未知")
        level = role.get("gameLevel", "??")
        active_day = role.get("activeDay", "??")
        
        # 针对不同游戏展示不同数据
        role_desc = (
            f"🎮 游戏: {game_name}\n"
            f"👤 角色: {role_name}\n"
            f"🆔 UID: {role_id}\n"
            f"🌏 服务器: {server_name}\n"
            f"📊 等级: {level}\n"
            f"📅 活跃天数: {active_day}天"
        )
        
        # 战双特有
        if role.get("gameId") == 2:
            role_desc += f"\n👗 涂装收集率: {role.get('fashionCollectionPercent', 0)*100:.1f}%"
        
        # 鸣潮特有
        if role.get("gameId") == 3:
            role_desc += f"\n🏆 成就数: {role.get('achievementCount', 0)}\n"
            role_desc += f"👻 声骸收集率: {role.get('phantomPercent', 0)*100:.1f}%"

        result.append(role_desc)
        result.append("-" * 20)
    
    # 移除最后一个分隔符
    if len(result) > 1:
        result.pop()
        
    result.append("===========================")
    
    return "\n".join(result)
