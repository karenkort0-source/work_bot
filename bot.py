import logging
import os
import httpx
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 配置 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_BASE_URL = "https://api.manus.ai/v1/tasks"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    # 1. 发送初步提醒
    placeholder_msg = await update.message.reply_text("🔍 Manus 正在思考并执行任务，请稍候...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 第一步：创建任务
            response = await client.post(API_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("task_id")

            if not task_id:
                await placeholder_msg.edit_text("❌ 任务创建失败，请稍后重试。")
                return

            # 第二步：轮询 (Polling) 检查结果
            # 我们每 5 秒检查一次，最多检查 20 次（共 100 秒）
            for i in range(20):
                await asyncio.sleep(5) 
                
                # 请求任务详情
                status_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                # 提取状态和结果 (具体字段根据 Manus 最新文档调整)
                status = status_data.get("status") # 比如 'completed'
                result_text = status_data.get("result") or status_data.get("response")

                if result_text:
                    await placeholder_msg.edit_text(result_text)
                    return
                
                if status == "failed":
                    await placeholder_msg.edit_text("❌ Manus 执行任务失败了。")
                    return
                
                # 如果还在跑，更新一下提示让用户别急
                if i % 4 == 0:
                    await placeholder_msg.edit_text(f"⏳ Manus 还在努力中 (已耗时 {i*5}s)...")

            await placeholder_msg.edit_text(f"⌛ 任务处理时间较长，请稍后直接访问链接查看：\n{task_data.get('task_url')}")

    except Exception as e:
        logger.error(f"出错: {e}")
        await placeholder_msg.edit_text("抱歉，暂时无法获取 Manus 的回答。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🤖 机器人已就绪，请提问！")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
