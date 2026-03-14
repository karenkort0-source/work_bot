import logging
import httpx
import os
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 配置区 ---
# 建议在 Railway Variables 页面确保变量名完全一致
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_AI_API_KEY = os.environ.get("MANUS_AI_API_KEY")
MANUS_AI_API_URL = "https://api.manus.ai/v1/tasks"

# 日志设置
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """响应 /start 命令"""
    user = update.effective_user
    await update.message.reply_html(
        f"你好, {user.mention_html()}! 我是 Manus AI 助手，请直接给我发送消息。"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """响应 /help 命令"""
    await update.message.reply_text("只需向我发送文本消息，我会将其转发给 Manus AI。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理消息并异步转发至 Manus AI"""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    if not user_message:
        return

    logger.info(f"收到来自 {chat_id} 的消息: {user_message}")

    if not MANUS_AI_API_KEY:
        logger.error("MANUS_AI_API_KEY 未设置")
        await update.message.reply_text("错误：Manus AI API-Key 未配置，请在服务器设置环境变量。")
        return

    headers = {
        "API_KEY": MANUS_AI_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": user_message,
        "taskMode": "chat",
        "agentProfile": "speed",
    }

    # 使用 httpx 异步请求，防止群组卡顿
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MANUS_AI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            manus_response = response.json()
            
            # 兼容不同的返回格式
            ai_reply = manus_response.get("result") or manus_response.get("response") or "未能获取有效回复"
            await update.message.reply_text(ai_reply)

    except Exception as e:
        logger.error(f"请求失败: {e}")
        await update.message.reply_text("抱歉，连接 Manus AI 时发生错误。")

def main() -> None:
    """启动机器人"""
    # 强制检查 Token
    if not TELEGRAM_BOT_TOKEN:
        logger.error("!!! 致命错误: 无法读取 TELEGRAM_BOT_TOKEN !!!")
        logger.info("请检查 Railway 后台 Variables 是否添加了该变量。")
        sys.exit(1)

    logger.info("正在启动机器人...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 开始轮询
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
