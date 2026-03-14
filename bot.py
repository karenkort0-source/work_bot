import logging
import os
import httpx
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 极速配置 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_BASE_URL = "https://api.manus.ai/v1/tasks"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def fast_parse(result_data):
    """极速解析：只要有内容就提取，不管任务是否完全结束"""
    if not result_data or not isinstance(result_data, list):
        return None
    for item in reversed(result_data):
        if item.get("role") == "assistant":
            contents = item.get("content", [])
            texts = [c.get("text") for c in contents if c.get("type") == "output_text" and c.get("text")]
            if texts:
                return "\n".join(texts).strip()
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    # 1. 立即响应
    status_msg = await update.message.reply_text("⚡ 正在联络 Manus...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 第一步：极速提交
            resp = await client.post(API_BASE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            task_info = resp.json()
            task_id = task_info.get("task_id")

        # 第二步：高频轮询（前30秒每2秒查一次，追求极限速度）
        async with httpx.AsyncClient(timeout=10.0) as check_client:
            for i in range(50): 
                await asyncio.sleep(2) 
                
                try:
                    s_res = await check_client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                    s_data = s_res.json()
                    
                    # 只要拿到文字内容，立刻更新并结束对话
                    answer = fast_parse(s_data.get("result"))
                    if answer:
                        await status_msg.edit_text(answer)
                        return
                    
                    # 如果 Manus 明确报错
                    if s_data.get("status") in ["failed", "error"]:
                        await status_msg.edit_text("❌ Manus 任务执行中断。")
                        return

                except Exception as e:
                    logger.error(f"轮询微报错: {e}")
                    continue

            await status_msg.edit_text(f"⌛ 任务处理中，请查看：\n{task_info.get('task_url')}")

    except Exception as e:
        logger.error(f"连接失败: {e}")
        await status_msg.edit_text("⚠️ 访问超时，请重试。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("✅ 极速版已就绪。")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
