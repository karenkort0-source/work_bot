import logging
import requests
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MANUS_AI_API_KEY = os.getenv("MANUS_AI_API_KEY")
MANUS_AI_API_URL = os.getenv("MANUS_AI_API_URL")

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}! Я бот, который поможет тебе общаться с Manus AI."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text("Просто отправь мне сообщение, и я перешлю его Manus AI.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages and forward to Manus AI."""
    user_message = update.message.text
    chat_id = update.effective_chat.id

    if not user_message:
        await update.message.reply_text("Пожалуйста, отправьте текстовое сообщение.")
        return

    logger.info(f"Получено сообщение от {chat_id}: {user_message}")

    if not MANUS_AI_API_KEY:
        logger.error("MANUS_AI_API_KEY не установлен.")
        await update.message.reply_text("Извините, API-ключ Manus AI не настроен. Пожалуйста, сообщите администратору.")
        return

    if not MANUS_AI_API_URL:
        logger.error("MANUS_AI_API_URL не установлен.")
        await update.message.reply_text("Извините, URL Manus AI не настроен. Пожалуйста, сообщите администратору.")
        return

    headers = {
        "API_KEY": f"{MANUS_AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "prompt": user_message,
        "attachments": [],
        "taskMode": "chat",
        "connectors": [],
        "hideInTaskList": True,
        "createShareableLink": True,
        "taskId": "",
        "agentProfile": "speed",
        "locale": ""
    }

    try:
        response = requests.post(MANUS_AI_API_URL, headers=headers, json=payload)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        manus_response = response.json()
        logger.info(f"Ответ от Manus AI: {manus_response}")

        ai_reply = manus_response.get("result", manus_response.get("response", "Извините, не удалось получить ответ от Manus AI."))
        
        await update.message.reply_text(ai_reply)

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к Manus AI: {e}")
        await update.message.reply_text("Извините, произошла ошибка при обращении к Manus AI.")
    except Exception as e:
        logger.error(f"Неизвестная ошибка: {e}")
        await update.message.reply_text("Извините, произошла непредвиденная ошибка.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

