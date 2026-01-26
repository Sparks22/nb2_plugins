from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.params import CommandArg
import sys
from pathlib import Path

# 确保能找到同级模块
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.append(str(current_dir))

# 导入我们在 ww_db_helper.py 中实例化的 db 对象
try:
    from ww_db_helper import db
except ImportError:
    try:
        from .ww_db_helper import db
    except ImportError:
        from src.plugins.ww_db_helper import db

from nonebot import get_driver

driver = get_driver()

@driver.on_startup
async def init_demo_tables():
    # 创建演示用的笔记表
    await db.create_table("""
        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

# 定义命令
add_note = on_command("记录", priority=5)
get_notes = on_command("查询记录", priority=5)

@add_note.handle()
async def _(args: Message = CommandArg()):
    content = args.extract_plain_text().strip()
    if not content:
        await add_note.finish("请输入要记录的内容，例如：记录 今天天气不错")
        return
    
    # 模拟获取 user_id (在真实 NoneBot 事件中可以从 event 获取)
    # 这里为了演示简单，我们假设是从 event 获取的，但因为这里没有定义 event 参数，
    # 实际运行时请加上 event: GroupMessageEvent 并使用 event.user_id
    # 下面仅作演示逻辑
    
    # 执行插入 SQL
    sql = "INSERT INTO user_notes (user_id, content) VALUES (?, ?)"
    # 这里我们写死一个 user_id 用于测试，实际使用请换成 event.user_id
    user_id = 123456 
    
    await db.execute_update(sql, (user_id, content))
    await add_note.finish(f"已记录：{content}")

@get_notes.handle()
async def _():
    # 执行查询 SQL
    sql = "SELECT * FROM user_notes ORDER BY created_at DESC LIMIT 5"
    rows = await db.fetch_all(sql)
    
    if not rows:
        await get_notes.finish("暂无记录")
        return
    
    msg_list = ["📝 最新 5 条记录："]
    for row in rows:
        msg_list.append(f"[{row['created_at']}] {row['content']}")
    
    await get_notes.finish("\n".join(msg_list))
