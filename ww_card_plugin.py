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
        # 最后尝试全路径（假设在 src.plugins 下）except ImportError:
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
    # 检查用户是否已绑定
    user_id = event.user_id
    row = await db.fetch_one("SELECT game_uid FROM user_bind WHERE user_id = ?", (user_id,))
    
    if not row:
        await ww_card_plugin.finish("您尚未绑定游戏UID，无法查询卡片。\n请发送 '绑定+UID' 进行绑定，例如：绑定100123456")
        return

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
        img_bytes = generate_card_image(data, game_name)
        
        if img_bytes:
             # 回复图片
             await ww_card_plugin.finish(MessageSegment.at(event.user_id) + MessageSegment.image(img_bytes))
        else:
             await ww_card_plugin.finish(f"未找到相关 {game_name} 角色信息或生成图片失败")
            
    except Exception as e:
        # await ww_card_plugin.finish(f"请求发生错误: {str(e)}")
        pass

import io
from PIL import Image, ImageDraw, ImageFont

def generate_card_image(data: dict, game_name: str) -> bytes:
    """
    生成角色卡片图片
    :return: 图片的 bytes 数据
    """
    if not data.get("success"):
        return None
    
    role_list = data.get("data", [])
    target_game_id = 3 if game_name == "鸣潮" else 2
    filtered_list = [r for r in role_list if r.get("gameId") == target_game_id]
    
    if not filtered_list:
        return None

    # 图片配置
    width = 600
    # 根据角色数量动态计算高度，每个角色大约占用 250px，加上头部和底部
    card_height = 280
    height = 100 + (len(filtered_list) * card_height)
    
    # 背景颜色 (淡色背景)
    bg_color = (240, 248, 255) if game_name == "鸣潮" else (40, 40, 45) # 鸣潮偏亮，战双偏暗
    text_color = (0, 0, 0) if game_name == "鸣潮" else (255, 255, 255)
    accent_color = (0, 191, 255) if game_name == "鸣潮" else (220, 20, 60) # 鸣潮蓝，战双红
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # 尝试加载中文字体，如果失败则使用默认
    try:
        # 尝试 Windows 常见中文字体
        font_title = ImageFont.truetype("msyhbd.ttc", 36)
        font_content = ImageFont.truetype("msyh.ttc", 24)
        font_small = ImageFont.truetype("msyh.ttc", 20)
    except:
        try:
             # 尝试 Linux 常见字体
            font_title = ImageFont.truetype("NotoSansCJK-Bold.ttc", 36)
            font_content = ImageFont.truetype("NotoSansCJK-Regular.ttc", 24)
            font_small = ImageFont.truetype("NotoSansCJK-Regular.ttc", 20)
        except:
            # 降级
            font_title = ImageFont.load_default()
            font_content = ImageFont.load_default()
            font_small = ImageFont.load_default()

    # 绘制标题
    title = f"{game_name} 角色卡片"
    # 获取文本宽高 (兼容旧版 Pillow)
    bbox = draw.textbbox((0, 0), title, font=font_title)
    text_w = bbox[2] - bbox[0]
    draw.text(((width - text_w) / 2, 30), title, font=font_title, fill=text_color)
    
    y_offset = 100
    
    for role in filtered_list:
        # 绘制单个角色卡片背景
        # draw.rectangle([20, y_offset, width-20, y_offset + card_height - 20], outline=accent_color, width=2)
        
        # 角色名
        role_name = role.get("roleName", "未知")
        draw.text((40, y_offset), f"角色: {role_name}", font=font_content, fill=text_color)
        
        # 等级 (画在右侧)
        level = role.get("gameLevel", "??")
        draw.text((width - 150, y_offset), f"Lv.{level}", font=font_content, fill=accent_color)
        
        y_cursor = y_offset + 40
        
        # 详细信息
        role_id = role.get("roleId", "未知")
        server_name = role.get("serverName", "未知")
        
        draw.text((40, y_cursor), f"UID: {role_id}", font=font_small, fill=text_color)
        draw.text((300, y_cursor), f"服务器: {server_name}", font=font_small, fill=text_color)
        y_cursor += 35
        
        # 特有数据
        if game_name == "战双帕弥什":
            fashion = role.get('fashionCollectionPercent', 0) * 100
            score = role.get('roleScore', '暂无')
            draw.text((40, y_cursor), f"涂装收集: {fashion:.1f}%", font=font_small, fill=text_color)
            draw.text((300, y_cursor), f"战力评分: {score}", font=font_small, fill=text_color)
            
        elif game_name == "鸣潮":
            achieve = role.get('achievementCount', 0)
            phantom = role.get('phantomPercent', 0) * 100
            draw.text((40, y_cursor), f"成就数: {achieve}", font=font_small, fill=text_color)
            draw.text((300, y_cursor), f"声骸收集: {phantom:.1f}%", font=font_small, fill=text_color)
            
        # 分割线
        y_offset += card_height
        draw.line([40, y_offset - 20, width - 40, y_offset - 20], fill=accent_color, width=1)

    # 转换为 bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()

