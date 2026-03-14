import logging
import os
import httpx
import asyncio
import sys
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- 1. 配置 ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MANUS_KEY = os.environ.get("MANUS_AI_API_KEY")
API_BASE_URL = "https://api.manus.ai/v1/tasks"

# 内存记忆：支持群组内多人协作，每个人/群共享对话上下文
chat_threads = {}

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def fast_extract(result_data):
    """极限提取：从 Manus 复杂的 JSON 中抓取最新的助手对话内容"""
    if not isinstance(result_data, list): return None
    # 倒序检索，只要看到 assistant 有文字输出，立刻抓取
    for item in reversed(result_data):
        if item.get("role") == "assistant":
            contents = item.get("content", [])
            texts = [c.get("text") for c in contents if c.get("type") == "output_text" and c.get("text")]
            if texts:
                return "\n".join(texts).strip()
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 使用 chat_id 作为 key，这样群里所有人发消息都能共享同一个 Manus 对话上下文
    chat_id = update.effective_chat.id
    user_text = update.message.text
    if not user_text or not MANUS_KEY: return

    headers = {"API_KEY": MANUS_KEY, "Content-Type": "application/json"}
    
    # 构造请求：如果有 thread_id 则带上，实现深入对话
    payload = {"prompt": user_text, "taskMode": "chat"}
    if chat_id in chat_threads:
        payload["thread_id"] = chat_threads[chat_id]

    # 发送一个初始状态，减少群员焦虑
    status_msg = await update.message.reply_text("⚡ Manus 正在处理中...")

    try:
        # 使用极短的连接超时，追求首字节响应速度
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
        async with httpx.AsyncClient(timeout=10.0, limits=limits) as client:
            # 第一步：极速创建任务
            resp = await client.post(API_BASE_URL, headers=headers, json=payload)
            resp.raise_for_status()
            res_json = resp.json()
            task_id = res_json.get("task_id")
            
            # 保存 thread_id 确保后续对话具有连续性
            if "thread_id" in res_json:
                chat_threads[chat_id] = res_json["thread_id"]

            # 第二步：高频动态轮询（抢断模式）
            # 前 20 秒每 1.5 秒查一次，这是为了保证在 Manus 官网出结果的瞬间，TG 也能刷出来
            start_time = time.time()
            for i in range(80): 
                await asyncio.sleep(1.5 if i < 15 else 3)
                
                try:
                    s_res = await client.get(f"{API_BASE_URL}/{task_id}", headers=headers)
                    s_data = s_res.json()
                    
                    # 只要提取到结果，立即更新消息并结束本次等待
                    answer = fast_extract(s_data.get("result"))
                    if answer:
                        # 如果内容太长，TG 编辑消息会报错，这里做了简单保护
                        if len(answer) > 4000: answer = answer[:4000] + "..."
                        await status_msg.edit_text(answer)
                        logger.info(f"任务 {task_id} 已反馈给群组，耗时 {time.time()-start_time:.2f}s")
                        return
                    
                    # 检查是否失败
                    if s_data.get("status") in ["failed", "error"]:
                        await status_msg.edit_text("❌ Manus 在执行过程中遇到了错误。")
                        return
                except Exception as e:
                    logger.warning(f"轮询尝试 {i} 出错: {e}")
                    continue

            await status_msg.edit_text(f"⌛ 任务处理较慢，请点击链接查看实时进展：\n{res_json.get('task_url')}")

    except Exception as e:
        logger.error(f"严重错误: {e}")
        await status_msg.edit_text("⚠️ 连接 Manus 超时，请稍后重试。")

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in chat_threads:
        del chat_threads[chat_id]
    await update.message.reply_text("🧹 该群组的 Manus 记忆已清除，可以开始新任务了！")

def main():
    if not TOKEN: sys.exit(1)
    # 允许并发处理，这样群里多个人说话不会互相排队阻塞
    app = Application.builder().token(TOKEN).concurrent_updates(True).build()
    
    app.add_handler(CommandHandler("start", lambda u, c: u.message.reply_text("✅ 工作群协作模式已开启。")))
    app.add_handler(CommandHandler("reset", reset_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started for group collaboration...")
    app.run_polling()

if __name__ == "__main__":
    main()
