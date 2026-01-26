from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.rule import to_me
from nonebot.typing import T_State
import json
from wwSrcoe import send_kuro_request

# 定义常量
API_URL = "https://api.kurobbs.com/user/role/findUserDefaultRole"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.eyJjcmVhdGVkIjoxNzY4NjQ1NjcxNDkxLCJ1c2VySWQiOjIwOTEwNTM1fQ.YD3jbfC02hNPzbrprnPiu1vgKB02eesWbRAChHk6Q64"
METHOD = "POST"

async def check_rule(event: GroupMessageEvent) -> bool:
    """
    检查规则：
    1. 用户 @ 机器人 (由 to_me() 处理)
    2. 消息内容以 "查看" 开头
    """
    msg = event.get_plaintext().strip()
    return msg.startswith("查看") and len(msg) > 2

# 注册消息响应器
ww_query_plugin = on_message(rule=to_me() & check_rule, priority=10, block=True)

@ww_query_plugin.handle()
async def handle_request(bot: Bot, event: GroupMessageEvent, state: T_State):
    # 解析消息内容，提取 queryUserId
    msg = event.get_plaintext().strip()
    query_user_id = msg.replace("查看", "").strip()
    
    if not query_user_id:
        await ww_query_plugin.finish("请在“查看”后面附带要查询的用户ID")
        return

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
        
        # 回复用户
        await ww_query_plugin.finish(MessageSegment.at(event.user_id) + result_msg)
            
    except Exception as e:
        # await ww_query_plugin.finish(f"请求发生错误: {str(e)}")
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
