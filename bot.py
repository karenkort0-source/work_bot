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

def extract_content(data):
    """专门从那堆乱七八糟的 JSON 里提取助手的纯文字回复"""
    try:
        # 如果是列表格式（对应你截图里的情况）
        if isinstance(data, list):
            for item in data:
                # 找角色是 assistant 的消息
                if item.get("role") == "assistant":
                    contents = item.get("content", [])
                    # 提取文字内容
                    text_parts = [c.get("text") for c in contents if c.get("type") == "output_text"]
                    return "\n".join(text_parts)
        # 如果是字典格式
        elif isinstance(data, dict):
            return data.get("result") or data.get("output") or str(data)
    except Exception as e:
        logger.error(f"解析出错: {e}")
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    placeholder_msg = await update.message.reply_text("🔍 Manus 正在处理中...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 1. 提交任务
            response = await client.post(API_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            task_id = response.json().get("task_id")

            # 2. 轮询监工
            for i in range(30):
                await asyncio.sleep(6) 
                status_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                # 核心步骤：提取纯文字结果
                # 根据你截图的结构，结果通常在 'result' 字段里，它是一个列表
                raw_result = status_data.get("result")
                clean_text = extract_content(raw_result)

                if clean_text:
                    await placeholder_msg.edit_text(clean_text)
                    return
                
                if status_data.get("status") in ["failed", "error"]:
                    await placeholder_msg.edit_text("❌ Manus 执行失败。")
                    return
                
                # 动态加载提示
                if i % 2 == 0:
                    await placeholder_msg.edit_text(f"⏳ 正在生成答案... ({i*6}s)")

            await placeholder_msg.edit_text("⌛ 响应时间过长，请稍后再试。")

    except Exception as e:
        logger.error(f"出错: {e}")
        await placeholder_msg.edit_text("抱歉，回复失败了。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🤖 已就绪，请提问。")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
