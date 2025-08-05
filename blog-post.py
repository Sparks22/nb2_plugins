import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request
from nonebot import get_driver, get_bot, get_bots
from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot
from nonebot.adapters.telegram import Bot as TelegramBot
from nonebot.plugin import PluginMetadata
from nonebot.log import logger
import uvicorn

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="博客文章推送",
    description="接收GitHub Webhook并推送博客文章更新到QQ群",
    usage="自动接收Webhook推送",
    homepage=None,
    type="application",
    config=None,
    supported_adapters=None,
)

# 硬编码的群组配置（完全按照原Koishi插件逻辑）
# QQ群组配置
QQ_TARGET_GROUPS = [
    "1051035890", 
    "1051639698",  
    "811724851",
    "1054446974",
    "165624236"
]

# Telegram群组配置（负数格式）
TG_TARGET_GROUPS = [
     "-1002483879845",  # 示例Telegram群组ID，请替换为实际的群组ID
    # "-1009876543210",  # 可以添加多个Telegram群组
]

# 调试模式开关（完全按照原Koishi插件逻辑）
DEBUG_MODE = True

# 消息发送延迟配置（秒）
MESSAGE_DELAY_SECONDS = 120

# 获取驱动器
driver = get_driver()

# 创建独立的FastAPI应用（按照Koishi插件逻辑）
app = FastAPI(title="Blog Post Webhook Server")

# 完全按照原Koishi插件的端口配置
WEBHOOK_PORT = 15667  # 原Koishi插件使用的端口


def log_webhook_data(data: Dict[str, Any]) -> None:
    """记录Webhook数据到日志文件（完全按照原Koishi插件逻辑）"""
    if DEBUG_MODE:
        # 确保log.txt文件存在
        log_path = os.path.join(os.path.dirname(__file__), '..', '..', 'log.txt')
        if not os.path.exists(log_path):
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write('')
        
        # 写入日志文件
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {json.dumps(data, indent=2, ensure_ascii=False)}\n\n"
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)


# 原Koishi插件的函数已经直接集成到webhook_handler中


async def send_to_groups(message: str) -> None:
    """发送消息到配置的QQ群和Telegram群组"""
    if not message:
        return
    
    total_groups = len(QQ_TARGET_GROUPS) + len(TG_TARGET_GROUPS)
    logger.info(f"准备发送消息到 {total_groups} 个群组 (QQ: {len(QQ_TARGET_GROUPS)}, TG: {len(TG_TARGET_GROUPS)})")
    
    # 获取所有Bot实例
    bots = get_bots()
    
    # 发送到QQ群组
    onebot_bots = [bot for bot in bots.values() if isinstance(bot, OneBotV11Bot)]
    if onebot_bots and QQ_TARGET_GROUPS:
        onebot_bot = onebot_bots[0]  # 使用第一个OneBot实例
        for group_id in QQ_TARGET_GROUPS:
            try:
                await onebot_bot.send_group_msg(group_id=int(group_id), message=message)
                logger.info(f"成功发送消息到QQ群组 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到QQ群组 {group_id} 失败: {str(e)}")
    elif QQ_TARGET_GROUPS:
        logger.warning("未找到OneBot实例，无法发送到QQ群组")
    
    # 发送到Telegram群组
    telegram_bots = [bot for bot in bots.values() if isinstance(bot, TelegramBot)]
    if telegram_bots and TG_TARGET_GROUPS:
        telegram_bot = telegram_bots[0]  # 使用第一个Telegram实例
        for group_id in TG_TARGET_GROUPS:
            try:
                await telegram_bot.send_message(chat_id=int(group_id), text=message)
                logger.info(f"成功发送消息到Telegram群组 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到Telegram群组 {group_id} 失败: {str(e)}")
    elif TG_TARGET_GROUPS:
        logger.warning("未找到Telegram实例，无法发送到Telegram群组")


@app.post("/")
async def webhook_handler(request: Request):
    """处理GitHub Webhook请求（完全按照原Koishi插件逻辑）"""
    try:
        # 获取请求数据
        body = await request.body()
        content_type = request.headers.get('content-type', '')
        
        if 'application/json' in content_type:
            payload = json.loads(body)
        elif 'application/x-www-form-urlencoded' in content_type:
            form_data = await request.form()
            payload_str = form_data.get('payload')
            if payload_str:
                payload = json.loads(payload_str)
            else:
                payload = dict(form_data)
        else:
            payload = json.loads(body)
        
        # 记录调试信息（完全按照原Koishi插件逻辑）
        log_webhook_data(payload)
        # logger.info(f"收到 Webhook: {payload if DEBUG_MODE else '(调试模式未开启)'}")
        
        # 返回状态（完全按照原Koishi插件逻辑）
        response_data = {"status": "ok"}
        
        # 处理GitHub Ping事件（完全按照原Koishi插件逻辑）
        if payload.get('zen'):
            logger.info(f"收到 GitHub Ping: {payload['zen']}")
            return response_data
        
        # 处理提交事件（完全按照原Koishi插件逻辑）
        if payload.get('ref') and payload.get('commits'):
            # 过滤以 'posts:' 开头的提交
            posts_commits = [commit for commit in payload['commits'] 
                           if commit['message'].lower().startswith('posts:')]
            
            # 过滤以 'update:' 开头的提交
            update_commits = [commit for commit in payload['commits'] 
                            if commit['message'].lower().startswith('update:')]
            
            message = None
            
            # 处理 posts: 提交（显示文章链接）
            if posts_commits:
                # 收集所有文章的URL和摘要
                all_posts = []
                summaries = set()
                
                for commit in posts_commits:
                    # 获取新增和修改的文件
                    commit_posts = []
                    for file in commit.get('added', []) + commit.get('modified', []):
                        if file.startswith('src/content/posts/'):
                            filename = file.replace('src/content/posts/', '').replace('.md', '')
                            commit_posts.append(f"https://2x.nz/posts/{filename}/")
                    
                    if commit_posts:
                        all_posts.extend(commit_posts)
                    # 提取摘要（去掉 'posts:' 前缀）
                    summary = commit['message'].replace('posts:', '', 1).strip()
                    if summary:
                        summaries.add(summary)
                
                if all_posts:
                    # 构建消息（完全按照原Koishi插件逻辑）
                    msg_parts = [
                        'AcoFork Blog Update！',
                        f'摘要：{"；".join(summaries)}',
                        '链接：'
                    ]
                    msg_parts.extend(all_posts)
                    message = '\n'.join(msg_parts)
                    
                    logger.info(f"检测到 {len(all_posts)} 篇文章更新，准备推送")
            
            # 处理 update: 提交（仅显示标题和摘要）
            elif update_commits:
                summaries = set()
                for commit in update_commits:
                    # 提取摘要（去掉 'update:' 前缀）
                    summary = commit['message'].replace('update:', '', 1).strip()
                    if summary:
                        summaries.add(summary)
                
                if summaries:
                    # 构建消息（仅显示标题和摘要）
                    msg_parts = [
                        'AcoFork Blog Update！',
                        f'摘要：{"；".join(summaries)}'
                    ]
                    message = '\n'.join(msg_parts)
                    
                    logger.info(f"检测到 update 提交，准备推送摘要信息")
            
            if message:
                # 延迟发送消息（可配置延迟时间）
                async def delayed_send():
                    await asyncio.sleep(MESSAGE_DELAY_SECONDS)  # 可配置延迟（秒）
                    await send_to_groups(message)
                
                # 创建后台任务
                asyncio.create_task(delayed_send())
                
                logger.info(f"预定{MESSAGE_DELAY_SECONDS}秒后发送消息到：QQ群组: {len(QQ_TARGET_GROUPS)}个，Telegram群组: {len(TG_TARGET_GROUPS)}个")
        
        return response_data
        
    except Exception as e:
        logger.error(f"Webhook 处理异常: {str(e)}")
        return {"status": "error", "message": str(e)}


# 独立HTTP服务器实例
webhook_server = None


async def start_webhook_server():
    """启动独立的Webhook服务器（按照Koishi插件逻辑）"""
    global webhook_server
    try:
        config = uvicorn.Config(
            app=app,
            host="::",
            port=WEBHOOK_PORT,
            log_level="info" if DEBUG_MODE else "warning",
            loop="auto",  # 建议明确写出，兼容性更好
        )
        webhook_server = uvicorn.Server(config)
        logger.info(f"启动独立Webhook服务器，端口: {WEBHOOK_PORT}")
        await webhook_server.serve()
    except Exception as e:
        logger.error(f"Webhook服务器启动失败: {str(e)}")


@driver.on_startup
async def startup():
    """插件启动时的初始化"""
    logger.info("博客推送插件已启动")
    logger.info(f"Webhook 服务器已启动，监听 http://0.0.0.0:{WEBHOOK_PORT}")
    logger.info(f"目标QQ群组: {', '.join(QQ_TARGET_GROUPS)}")
    logger.info(f"目标Telegram群组: {', '.join(TG_TARGET_GROUPS)}")
    logger.info(f"总群组数: {len(QQ_TARGET_GROUPS) + len(TG_TARGET_GROUPS)}个")
    logger.info(f"调试模式: {'开启' if DEBUG_MODE else '关闭'}")
    
    # 启动独立的Webhook服务器（按照Koishi插件逻辑）
    asyncio.create_task(start_webhook_server())


@driver.on_shutdown
async def shutdown():
    """插件关闭时的清理"""
    global webhook_server
    if webhook_server:
        logger.info("正在关闭Webhook服务器...")
        webhook_server.should_exit = True
    logger.info("博客推送插件已关闭")