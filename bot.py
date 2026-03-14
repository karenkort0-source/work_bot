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

# 用于存储每个用户的 thread_id，实现对话延续
# 注意：这在内存中存储，机器人重启会重置。如果需要永久记住，建议后续加数据库。
user_threads = {}

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def fast_extract(result_data):
    if not isinstance(result_data, list): return None
    for item in reversed(result_data):
        if item.get("role") == "assistant":
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content.get("text").strip()
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    
    # --- 关键修改：携带 thread_id 实现上下文延续 ---
    payload = {
        "prompt": user_text,
        "taskMode": "chat"
    }
    if user_id in user_threads:
        payload["thread_id"] = user_threads[user_id]

    status_msg = await update.message.reply_text("⚡ 思考中...")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(API_BASE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            res_json = resp.json()
            task_id = res_json.get("task_id")
            
            # 记录这次对话的 thread_id，下次提问时带上它
            if "thread_id" in res_json:
                user_threads[user_id] = res_json["thread_id"]
            
            # 高频轮询结果
            for i in range(60):
                await asyncio.sleep(1 if i < 15 else 2) 
                s_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                s_data = s_res.json()
                
                answer = fast_extract(s_data.get("result"))
                if answer:
                    await status_msg.edit_text(answer)
                    return
                
                if s_data.get("status") in ["failed", "error"]:
                    await status_msg.edit_text("❌ 执行中断。")
                    return

            await status_msg.edit_text("⌛ 任务较慢，请稍后...")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("⚠️ 接口连接超时。")

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """新增指令：用于清空记忆，开启新话题"""
    user_id = update.effective_user.id
    if user_id in user_threads:
        del user_threads[user_id]
    await update.message.reply_text("🧹 记忆已清除，我们可以开始新话题了！")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("✅ 已支持上下文对话。")))
    app.add_handler(CommandHandler("reset", reset_chat)) # 注册重置指令
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == "__main__":
    main()
