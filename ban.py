from nonebot import on_message, get_driver
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
import os
import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="消息过滤",
    description="检测消息中的敏感词并进行撤回和禁言处理",
    usage="自动检测群消息中的敏感词",
    homepage=None,
    type="application",
    config=None,
    supported_adapters=None,
)

# 获取插件目录
plugin_dir = Path(__file__).parent
ban_file_path = plugin_dir / "ban.txt"

# 敏感词列表
ban_words = set()

# 文件监控相关
file_observer = None

class BanFileHandler(FileSystemEventHandler):
    """ban.txt文件变化监控处理器"""
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path == str(ban_file_path):
            logger.info("检测到ban.txt文件变化，正在重新加载敏感词...")
            load_ban_words()

def load_ban_words():
    """加载敏感词列表"""
    global ban_words
    try:
        if ban_file_path.exists():
            with open(ban_file_path, 'r', encoding='utf-8') as f:
                ban_words = set(line.strip() for line in f if line.strip())
            logger.info(f"已加载 {len(ban_words)} 个敏感词")
        else:
            # 创建空的ban.txt文件
            with open(ban_file_path, 'w', encoding='utf-8') as f:
                f.write("# 在此文件中添加敏感词，每行一个\n")
                f.write("# 例如：\n")
                f.write("# 敏感词1\n")
                f.write("# 敏感词2\n")
            logger.info(f"已创建空的敏感词文件: {ban_file_path}")
            ban_words = set()
    except Exception as e:
        logger.error(f"加载敏感词文件失败: {e}")
        ban_words = set()

def check_message_content(message: str) -> str:
    """检查消息内容是否包含敏感词"""
    message_lower = message.lower()
    for word in ban_words:
        if word.lower() in message_lower:
            return word
    return ""

# 消息处理器
message_handler = on_message(priority=1, block=False)

@message_handler.handle()
async def handle_message(bot: Bot, event: Event):
    """处理消息事件"""
    # 只处理群消息
    if not isinstance(event, GroupMessageEvent):
        return
    
    # 获取消息内容
    message_text = event.get_plaintext()
    if not message_text:
        return
    
    # 检查是否包含敏感词
    banned_word = check_message_content(message_text)
    if not banned_word:
        return
    
    try:
        # 撤回消息
        await bot.delete_msg(message_id=event.message_id)
        logger.info(f"已撤回包含敏感词 '{banned_word}' 的消息，用户: {event.user_id}")
        
        # 禁言用户5分钟 (300秒)
        await bot.set_group_ban(
            group_id=event.group_id,
            user_id=event.user_id,
            duration=300
        )
        logger.info(f"已禁言用户 {event.user_id} 5分钟，原因: 发送敏感词 '{banned_word}'")
        
        # # 发送提示消息（可选）
        # await bot.send_group_msg(
        #     group_id=event.group_id,
        #     message=f"检测到敏感词，已撤回消息并禁言用户5分钟。"
        # )
        
    except Exception as e:
        logger.error(f"处理敏感词消息失败: {e}")

# 驱动器事件
driver = get_driver()

@driver.on_startup
async def startup():
    """插件启动时加载敏感词"""
    global file_observer
    logger.info("消息过滤插件已启动")
    load_ban_words()
    logger.info(f"敏感词文件路径: {ban_file_path}")
    
    # 启动文件监控
    try:
        event_handler = BanFileHandler()
        file_observer = Observer()
        file_observer.schedule(event_handler, str(plugin_dir), recursive=False)
        file_observer.start()
        logger.info("已启动ban.txt文件自动监控")
    except Exception as e:
        logger.error(f"启动文件监控失败: {e}")

@driver.on_shutdown
async def shutdown():
    """插件关闭时的清理"""
    global file_observer
    if file_observer:
        file_observer.stop()
        file_observer.join()
        logger.info("已停止文件监控")
    logger.info("消息过滤插件已关闭")

# 重新加载敏感词的命令（可选功能）
from nonebot import on_command
from nonebot.permission import SUPERUSER

reload_ban = on_command("reload_ban", permission=SUPERUSER, priority=1)

@reload_ban.handle()
async def handle_reload_ban(bot: Bot, event: Event):
    """重新加载敏感词列表"""
    load_ban_words()
    await reload_ban.send(f"已重新加载敏感词列表，当前共有 {len(ban_words)} 个敏感词")