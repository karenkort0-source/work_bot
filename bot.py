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

def fast_extract(result_data):
    """最快路径提取：只拿最新助手的纯文字"""
    if not isinstance(result_data, list): return None
    # 倒序查找，优先获取最新的 assistant 回复
    for item in reversed(result_data):
        if item.get("role") == "assistant":
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content.get("text").strip()
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    # 1. 立即反馈（降低用户感知的等待时间）
    status_msg = await update.message.reply_text("⚡ 发起任务...")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 第一步：极速创建
            resp = await client.post(API_BASE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            task_id = resp.json().get("task_id")
            
            # 2. 动态轮询（根据耗时自动调整频率）
            for i in range(60): # 最多持续轮询
                # 前 15 秒每秒查 1 次，15 秒后每 2 秒查 1 次
                await asyncio.sleep(1 if i < 15 else 2) 
                
                try:
                    s_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                    s_data = s_res.json()
                    
                    # 关键点：只要拿到文字，不论 status 是什么，立刻同步到 TG
                    answer = fast_extract(s_data.get("result"))
                    if answer:
                        await status_msg.edit_text(answer)
                        return
                    
                    # 报错处理
                    if s_data.get("status") in ["failed", "error"]:
                        await status_msg.edit_text("❌ Manus 执行过程中断，请重试。")
                        return

                except Exception as e:
                    logger.error(f"轮询抖动: {e}")
                    continue

            await status_msg.edit_text("⌛ 任务执行较慢，建议点开链接查看进度。")

    except Exception as e:
        logger.error(f"连接失败: {e}")
        await status_msg.edit_text("⚠️ 接口连接超时，请检查网络。")

def main():
    if not TOKEN: sys.exit(1)
    # 使用并发级别更高的 Application
    app = Application.builder().token(TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("✅ 极速稳定版已就绪。")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
