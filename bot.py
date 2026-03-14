import logging
import os
import httpx
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. 配置与环境变量 ---
# 从 Railway 的 Variables 读取
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_URL = "https://api.manus.ai/v1/tasks"

# 开启日志，方便在 Railway Logs 查看问题
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. 机器人功能逻辑 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 你好！Manus AI 机器人已在 Railway 云端就绪。请直接发送消息给我。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text: return

    # 检查 API Key 是否设置
    if not MANUS_KEY:
        await update.message.reply_text("❌ 错误：未配置 MANUS_AI_API_KEY，请检查 Railway 变量。")
        return

    logger.info(f"收到用户消息: {user_text}")

    # 发送请求给 Manus AI
    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # 提取回复内容
            ans = data.get("result") or data.get("response") or "Manus 暂无回复"
            await update.message.reply_text(ans)
    except Exception as e:
        logger.error(f"API 请求出错: {e}")
        await update.message.reply_text(f"抱歉，Manus 接口出错了: {str(e)}")

# --- 3. 启动入口 ---
def main():
    if not TOKEN:
        logger.error("!!! 没找到 TELEGRAM_BOT_TOKEN !!!")
        sys.exit(1)

    # 建立机器人
    app = Application.builder().token(TOKEN).build()

    # 注册处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("机器人正在启动轮询...")
    app.run_polling()

if __name__ == "__main__":
    main()
