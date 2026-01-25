import json
from pathlib import Path
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.adapters.onebot.v11.permission import GROUP
from nonebot.rule import Rule

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "chehui_config.json"

def load_config():
    """
    加载配置文件
    返回：(enabled_groups, trigger_words)
    """
    default_config = {
        "enabled_groups": [],
        "trigger_words": ["那咋了"]
    }
    
    if not CONFIG_FILE.exists():
        return default_config
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config
    except Exception:
        return default_config

async def check_rule(bot: Bot, event: GroupMessageEvent) -> bool:
    """
    自定义Rule逻辑：
    1. 检查是否为机器人自己发送的消息 (防止循环触发)
    2. 读取配置文件
    3. 检查群号是否在白名单内
    4. 检查消息内容是否包含触发词
    """
    # 0. 防止机器人自我触发
    # bot.self_id 是字符串，event.user_id 是整数，需要转换类型比较
    if str(event.user_id) == bot.self_id:
        return False

    config = load_config()
    enabled_groups = config.get("enabled_groups", [])
    trigger_words = config.get("trigger_words", ["那咋了"])

    # 如果群号不在白名单内，直接忽略（返回 False）
    if event.group_id not in enabled_groups:
        return False
    
    # 检查消息纯文本内容是否包含任意触发词
    msg_text = event.get_plaintext()
    for word in trigger_words:
        if word in msg_text:
            return True
            
    return False

# 注册消息响应器
# permission=GROUP: 仅允许群聊消息触发
# rule=Rule(check_rule): 应用自定义规则
# priority=10: 优先级
# block=True: 拦截后续事件
chehui_plugin = on_message(
    rule=Rule(check_rule),
    permission=GROUP,
    priority=10,
    block=True
)

@chehui_plugin.handle()
async def handle_chehui(bot: Bot, event: GroupMessageEvent):
    """
    处理函数：撤回、禁言、回复
    """
    # 1. 撤回消息
    try:
        await bot.delete_msg(message_id=event.message_id)
    except Exception:
        # 如果撤回失败（例如权限不足），暂不处理异常，继续执行后续逻辑
        pass

    # 2. 设置禁言时间 1 分钟 (60秒)
    try:
        await bot.set_group_ban(
            group_id=event.group_id,
            user_id=event.user_id,
            duration=60
        )
    except Exception:
        # 如果禁言失败（例如权限不足），暂不处理异常
        pass

    # 3. @这个人并发送消息
    msg = MessageSegment.at(event.user_id) + " 恭喜您触发禁言彩蛋1分钟！"
    await chehui_plugin.finish(msg)
