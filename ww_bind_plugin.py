from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.rule import to_me
import sys
from pathlib import Path

# 确保能找到同级模块
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# 导入数据库 helper
try:
    from ww_db_helper import db
except ImportError:
    try:
        from .ww_db_helper import db
    except ImportError:
        from src.plugins.ww_db_helper import db

# 在插件加载时初始化表结构
# 注意：NoneBot2 插件通常在 import 时执行顶层代码
# 为了确保表存在，我们需要在 import 时调用建表语句
# 或者使用 on_startup 钩子 (更推荐)

from nonebot import get_driver

driver = get_driver()

@driver.on_startup
async def init_tables():
    # 创建用户绑定表
    await db.create_table("""
        CREATE TABLE IF NOT EXISTS user_bind (
            user_id INTEGER PRIMARY KEY,
            game_uid TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

async def check_bind_rule(event: GroupMessageEvent) -> bool:
    """
    检查规则：
    1. 用户 @ 机器人
    2. 消息以 "绑定" 开头
    """
    msg = event.get_plaintext().strip()
    return msg.startswith("绑定")

# 注册消息响应器
ww_bind_plugin = on_message(rule=to_me() & check_bind_rule, priority=10, block=True)

@ww_bind_plugin.handle()
async def handle_bind(bot: Bot, event: GroupMessageEvent):
    # 解析消息内容
    msg = event.get_plaintext().strip()
    # 移除 "绑定" 前缀，获取后面的 ID
    game_uid = msg.replace("绑定", "").strip()
    
    if not game_uid:
        await ww_bind_plugin.finish("请在“绑定”后面附带您的游戏UID，例如：绑定100123456")
        return
        
    user_id = event.user_id
    
    try:
        # 使用 REPLACE INTO 语法，如果已存在则更新，不存在则插入
        # 注意：sqlite3 支持 REPLACE INTO，它会先删除旧记录再插入新记录
        # 或者使用 UPSERT 语法 (INSERT ... ON CONFLICT DO UPDATE)
        
        # 这里使用更通用的逻辑：先查询是否存在
        check_sql = "SELECT user_id FROM user_bind WHERE user_id = ?"
        existing = await db.fetch_one(check_sql, (user_id,))
        
        if existing:
            # 更新
            update_sql = "UPDATE user_bind SET game_uid = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
            await db.execute_update(update_sql, (game_uid, user_id))
            action = "更新"
        else:
            # 插入
            insert_sql = "INSERT INTO user_bind (user_id, game_uid) VALUES (?, ?)"
            await db.execute_update(insert_sql, (user_id, game_uid))
            action = "绑定"
            
        await ww_bind_plugin.finish(MessageSegment.at(user_id) + f"\n✅ {action}成功！\nQQ: {user_id}\nUID: {game_uid}")
        
    except Exception as e:
        await ww_bind_plugin.finish(f"绑定失败，数据库错误: {str(e)}")
