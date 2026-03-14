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

    # 1. 发送初始提醒
    placeholder_msg = await update.message.reply_text("🤖 Manus 已收到指令，正在思考中...")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # 第一步：提交任务
            response = await client.post(API_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            task_data = response.json()
            task_id = task_data.get("task_id")

            if not task_id:
                await placeholder_msg.edit_text("❌ 任务创建失败，请检查 API 配置。")
                return

            # 第二步：深度监工模式
            # 循环 30 次，每次等 6 秒，总共给它 3 分钟时间
            for i in range(30):
                await asyncio.sleep(6) 
                
                # 获取任务实时状态
                status_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                status_res.raise_for_status()
                status_data = status_res.json()
                
                # 打印日志（你在 Railway 后台能看到这个，方便查错）
                logger.info(f"检查任务 {task_id} 状态: {status_data.get('status')}")

                # 尝试抓取所有可能的回答字段
                ans = (
                    status_data.get("result") or 
                    status_data.get("output") or 
                    status_data.get("response") or
                    (status_data.get("data", {}) if isinstance(status_data.get("data"), dict) else {}).get("result")
                )

                if ans:
                    await placeholder_msg.edit_text(f"✅ Manus 回复：\n\n{ans}")
                    return
                
                # 如果任务明确失败了
                if status_data.get("status") in ["failed", "error"]:
                    await placeholder_msg.edit_text("❌ Manus 执行任务时遇到了困难，失败了。")
                    return
                
                # 动态提示
                if i % 2 == 0:
                    await placeholder_msg.edit_text(f"⏳ Manus 正在处理中... (已耗时 {i*6}s)\n你可以去网页看实时画面: {task_data.get('task_url')}")

            await placeholder_msg.edit_text(f"⌛ 任务太复杂了，3分钟还没跑完。请直接看网页吧：\n{task_data.get('task_url')}")

    except Exception as e:
        logger.error(f"出错: {e}")
        await placeholder_msg.edit_text(f"抱歉，连接 Manus 接口超时或出错。")

def main():
    if not TOKEN: sys.exit(1)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("🤖 机器人已上线，请提问！")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
