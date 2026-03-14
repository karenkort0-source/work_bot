import logging
import os
import httpx
import asyncio
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 基础配置 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_BASE_URL = "https://api.manus.ai/v1/tasks"

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_manus_result(result_data):
    """
    高度精准的解析器：专门从复杂嵌套中提取 assistant 的对话文本
    """
    if not result_data or not isinstance(result_data, list):
        return None
    
    # 倒序查找，通常最新的回答在最后
    for item in reversed(result_data):
        if item.get("role") == "assistant":
            contents = item.get("content", [])
            # 过滤出所有文本类型的输出
            text_list = [c.get("text") for c in contents if c.get("type") == "output_text" and c.get("text")]
            if text_list:
                return "\n".join(text_list).strip()
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text or not MANUS_KEY:
        return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    payload = {"prompt": user_text, "taskMode": "chat"}

    # 1. 立即反馈，给用户“快”的视觉感受
    status_msg = await update.message.reply_text("🤔 Manus 正在处理您的请求...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 第一步：创建任务
            response = await client.post(API_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            task_info = response.json()
            task_id = task_info.get("task_id")

            if not task_id:
                await status_msg.edit_text("❌ 任务创建失败，请检查 API Key。")
                return

            # 第二步：智能轮询
            # 频率：前 30 秒每 3 秒查一次（追求快），之后每 6 秒查一次
            for i in range(40):
                wait_time = 3 if i < 10 else 6
                await asyncio.sleep(wait_time)
                
                status_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                # 尝试解析内容
                answer = parse_manus_result(status_data.get("result"))
                status = status_data.get("status")

                # 如果拿到结果，立即显示并退出循环
                if answer:
                    await status_msg.edit_text(answer)
                    return
                
                # 状态检查
                if status == "failed":
                    await status_msg.edit_text("❌ Manus 任务执行失败。")
                    return
                
                # 每隔几次更新一下进度条，证明机器人没死机
                if i % 3 == 0:
                    await status_msg.edit_text(f"⏳ Manus 正在搜索/执行中... ({i*wait_time}s)")

            await status_msg.edit_text(f"⌛ 任务处理较慢，您可以点击链接查看：\n{task_info.get('task_url')}")

    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("抱歉，连接服务器超时。请稍后再试。")

def main():
    if not TOKEN: 
        logger.error("未找到 TELEGRAM_BOT_TOKEN")
        sys.exit(1)
        
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("👋 机器人已就绪，请直接发送问题。")))
    app
