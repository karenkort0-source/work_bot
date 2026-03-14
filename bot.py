import logging
import os
import httpx
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. 配置 ---
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

    # 先发个消息告诉大家机器人动起来了
    placeholder_msg = await update.message.reply_text("🔍 Manus 收到任务，正在努力执行中，请稍候...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 第一步：提交任务，拿到 task_id
            response = await client.post(API_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("task_id")

            if not task_id:
                await placeholder_msg.edit_text("❌ 任务发起失败，请检查 API 配置。")
                return

            # 第二步：开启“监工模式”轮询结果
            # 每 6 秒检查一次，最多检查 20 次（总共等 2 分钟）
            for i in range(20):
                await asyncio.sleep(6) 
                
                # 请求任务详情
                status_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                # 提取状态和结果
                status = status_data.get("status")
                # 这里的字段名取决于 Manus 的最新返回结构，通常是 result 或 output
                final_result = status_data.get("result") or status_data.get("output") or status_data.get("response")

                # 如果拿到结果了，直接发回群组
                if final_result:
                    await placeholder_msg.edit_text(final_result)
                    return
                
                # 如果任务失败了
                if status == "failed":
                    await placeholder_msg.edit_text("❌ 抱歉，Manus 没能完成这项任务。")
                    return
                
                # 动态提示进度，让群员不觉得机器人死机了
                if i % 3 == 0:
                    await placeholder_msg.edit_text(f"⏳ Manus 还在深思熟虑中... (已耗时 {i*6}秒)")

            # 如果超过 2 分钟还没跑完，就先给个链接保底
            await placeholder_msg.edit_text(f"⌛ 任务耗时太长了，请点击链接查看实时进展：\n{task_data.get('task_url')}")

    except Exception as e:
        logger.error(f"出错: {e}")
        await placeholder_msg.edit_text(f"抱歉，连接 Manus 接口时发生错误。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🤖 机器人已就绪！直接在群里提问吧。")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
