import logging
import os
import httpx
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 配置 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_URL = "https://api.manus.ai/v1/tasks"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Manus AI 已连接！请发送问题，我会为你生成任务链接。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Manus 返回原始数据: {data}")

            # --- 核心逻辑修改：提取任务链接 ---
            task_url = data.get("task_url")
            task_title = data.get("task_title", "新任务")
            
            if task_url:
                reply = f"✅ 任务已创建：{task_title}\n\n🔗 点击查看 Manus 的实时执行过程：\n{task_url}"
            else:
                # 兼容直接返回结果的情况
                reply = data.get("result") or data.get("response") or "任务已提交，但未获取到链接。"

            await update.message.reply_text(reply)
            
    except Exception as e:
        logger.error(f"API 请求失败: {e}")
        await update.message.reply_text("抱歉，连接 Manus 失败。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
