from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.rule import to_me
from nonebot.typing import T_State
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

# 定义常量
API_URL = "https://api.kurobbs.com/gamer/role/list"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJjcmVhdGVkIjoxNzY4NjQ1NjcxNDkxLCJ1c2VySWQiOjIwOTEwNTM1fQ.YD3jbfC02hNPzbrprnPiu1vgKB02eesWbRAChHk6Q64"
METHOD = "POST"

async def check_rule(event: GroupMessageEvent) -> bool:
    """
    检查规则：
    1. 用户 @ 机器人 (由 to_me() 处理)
    2. 消息内容为 "鸣潮卡片" 或 "战双卡片"
    """
    msg = event.get_plaintext().strip()
    return msg in ["鸣潮卡片", "战双卡片"]

# 注册消息响应器
ww_card_plugin = on_message(rule=to_me() & check_rule, priority=10, block=True)

@ww_card_plugin.handle()
async def handle_request(bot: Bot, event: GroupMessageEvent):
    # 解析消息内容，确定 gameId
    msg = event.get_plaintext().strip()
    
    game_id = 3 if msg == "鸣潮卡片" else 2
    game_name = "鸣潮" if game_id == 3 else "战双帕弥什"

    # 构造请求数据
    api_data = {
        "gameId": game_id
    }

    try:
        # 调用封装好的工具方法
        resp = await send_kuro_request(API_URL, METHOD, TOKEN, api_data)
        
        # 尝试解析 JSON
        try:
            data = resp.json()
        except json.JSONDecodeError:
            await ww_card_plugin.finish(f"查询失败：返回数据不是有效的 JSON\n{resp.text}")
            return

        # 解析并格式化结果
        result_msg = parse_card_data(data, game_name)
        
        # 回复用户
        await ww_card_plugin.finish(MessageSegment.at(event.user_id) + result_msg)
            
    except Exception as e:
        # await ww_card_plugin.finish(f"请求发生错误: {str(e)}")
        pass

def parse_card_data(data: dict, game_name: str) -> str:
    """
    将 API 返回的 JSON 数据解析为用户可读的文本
    """
    if not data.get("success"):
        msg = data.get("msg", "未知错误")
        return f"\n查询 {game_name} 卡片失败: {msg}"
    
    # 真实数据结构：data 是一个列表，直接包含角色信息
    role_list = data.get("data", [])
    
    if not role_list:
        return f"\n查询 {game_name} 卡片成功，但未找到绑定的角色信息"

    # 根据当前查询的游戏名称筛选结果（API 似乎返回所有游戏的卡片，需要前端过滤）
    target_game_id = 3 if game_name == "鸣潮" else 2
    filtered_list = [r for r in role_list if r.get("gameId") == target_game_id]
    
    if not filtered_list:
        return f"\n未找到您的 {game_name} 角色信息"

    result = [f"\n====== {game_name} 角色卡片 ======"]
    
    for role in filtered_list:
        # 提取字段
        role_name = role.get("roleName", "未知")
        role_id = role.get("roleId", "未知")
        server_name = role.get("serverName", "未知")
        level = role.get("gameLevel", "??")
        
        # 基础信息
        role_desc = (
            f"👤 角色: {role_name}\n"
            f"🆔 UID: {role_id}\n"
            f"🌏 服务器: {server_name}\n"
            f"📊 等级: {level}"
        )
        
        # 战双特有 (gameId=2)
        if role.get("gameId") == 2:
            role_desc += f"\n👗 涂装收集率: {role.get('fashionCollectionPercent', 0)*100:.1f}%"
            role_desc += f"\n⚔️ 战力评分: {role.get('roleScore', '暂无')}"
        
        # 鸣潮特有 (gameId=3)
        if role.get("gameId") == 3:
            role_desc += f"\n🏆 成就数: {role.get('achievementCount', 0)}"
            role_desc += f"\n👻 声骸收集率: {role.get('phantomPercent', 0)*100:.1f}%"

        result.append(role_desc)
        result.append("-" * 20)
    
    # 移除最后一个分隔符
    if len(result) > 1:
        result.pop()
        
    result.append("==========================")
    
    return "\n".join(result)
