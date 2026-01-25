import httpx
from pathlib import Path
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
from nonebot.rule import to_me

# 硬编码的 API 请求配置
API_URL = "https://api.kurobbs.com/user/role/findUserDefaultRole"
API_METHOD = "POST"

API_HEADERS = {
    "Host": "api.kurobbs.com",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "sec-ch-ua": '"Android WebView";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
    "source": "android",
    "b-at": "52d84678a02944be9ad024a273efef5a",
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; MEIZU 21 Pro Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Kuro/2.10.0 KuroGameBox/2.10.0",
    "sec-ch-ua-mobile": "?1",
    "Content-Type": "application/x-www-form-urlencoded",
    "did": "EE8A7E4C915F1CD7EDE605AEAB96D9FBF3C0915D",
    "Accept": "application/json, text/plain, */*",
    "devCode": "39.144.144.52, Mozilla/5.0 (Linux; Android 14; MEIZU 21 Pro Build/UKQ1.230917.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/117.0.0.0 Mobile Safari/537.36 Kuro/2.10.0 KuroGameBox/2.10.0",
    "token": "eyJhbGciOiJIUzI1NiJ9.eyJjcmVhdGVkIjoxNzY4NjQ1NjcxNDkxLCJ1c2VySWQiOjIwOTEwNTM1fQ.YD3jbfC02hNPzbrprnPiu1vgKB02eesWbRAChHk6Q64",
    "sec-ch-ua-platform": '"Android"',
    "Origin": "https://web-static.kurobbs.com",
    "X-Requested-With": "com.kurogame.kjq",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

async def check_rule(event: GroupMessageEvent) -> bool:
    """
    检查规则：
    1. 用户 @ 机器人 (由 to_me() 处理)
    2. 消息内容以 "查看" 开头
    """
    msg = event.get_plaintext().strip()
    return msg.startswith("查看") and len(msg) > 2

# 注册消息响应器
# rule=to_me(): 必须 @ 机器人
# priority=10: 优先级
# block=True: 拦截后续事件
ww_request_plugin = on_message(rule=to_me() & check_rule, priority=10, block=True)

@ww_request_plugin.handle()
async def handle_request(bot: Bot, event: GroupMessageEvent):
    # 解析消息内容，提取 queryUserId
    # 格式示例："查看31312167"
    msg = event.get_plaintext().strip()
    query_user_id = msg.replace("查看", "").strip()
    
    if not query_user_id:
        await ww_request_plugin.finish("请在“查看”后面附带要查询的用户ID")
        return

    # 构造请求数据
    api_data = {
        "queryUserId": query_user_id
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = None
            if API_METHOD == "POST":
                # POST 请求，携带 headers 和 data
                resp = await client.post(API_URL, headers=API_HEADERS, data=api_data, timeout=10)
            else:
                # GET 请求
                resp = await client.get(API_URL, headers=API_HEADERS, params=api_data, timeout=10)
                
            result_text = resp.text
            
            # 直接回复结果并 @用户
            msg = MessageSegment.at(event.user_id) + f"\n查询ID: {query_user_id}\n请求状态码: {resp.status_code}\n返回结果:\n{result_text}"
            await ww_request_plugin.finish(msg)
            
    except Exception as e:
        # await ww_request_plugin.finish(f"请求失败: {str(e)}")
        pass
