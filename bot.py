import logging
import os
import httpx
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. 自动读取 Railway 环境变量 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_URL = "https://api.manus.ai/v1/tasks"

# 日志配置：在 Railway 的 Logs 页面可以看到这些输出
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 2. 核心功能逻辑 ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """响应 /start 命令"""
    await update.message.reply_text("👋 你好！Manus AI 机器人已在 Railway 云端就绪。\n直接给我发送消息，我帮你问 Manus。")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息"""
    user_text = update.message.text
    if not user_text:
        return

    # 检查 Key 是否填了
    if not MANUS_KEY:
        await update.message.reply_text("❌ 错误：未配置 MANUS_AI_API_KEY，请在 Railway 变量中添加。")
        return

    logger.info(f"收到用户消息: {user_text}")

    # 构造请求头和数据包
    headers = {
        "API_KEY": MANUS_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": user_text,
        "taskMode": "chat",
        "agentProfile": "speed"
    }

    try:
        # 使用异步请求，防止群组内多人使用时卡顿
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(API_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # 在日志中打印原始数据，方便出问题时排查
            logger.info(f"Manus 返回原始数据: {data}")

            # --- 智能字段提取逻辑 ---
            # 依次尝试 Manus 可能返回结果的各种字段名
            ans = (
                data.get("result") or 
                data.get("output") or 
                data.get("response") or 
                data.get("message")
            )
            
            # 如果结果在 data 嵌套层里
            if not ans and "data" in data:
                inner_data = data.get("data")
                if isinstance(inner_data, dict):
                    ans = inner_data.get("result") or inner_data.get("output")
                else:
                    ans = str(inner_data)

            # 实在找不到字段时的备选方案
            if not ans:
                ans = "⚠️ Manus 响应成功，但返回格式无法解析。请检查 Railway 日志中的 '原始数据'。"

            await update.message.reply_text(ans)

    except Exception as e:
        logger.error(f"API 请求失败: {e}")
        await update.message.reply_text(f"抱歉，连接 Manus 出错了: {str(e)}")

# --- 3. 启动程序 ---

def main():
    if not TOKEN:
        logger.error("!!! 致命错误: 没找到 TELEGRAM_BOT_TOKEN !!!")
        sys.exit(1)

    # 建立与 Telegram 的连接
    app = Application.builder().token(TOKEN).build()

    # 绑定指令和消息处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("机器人启动成功，正在云端监听消息...")
    app.run_polling()

if __name__ == "__main__":
    main()
