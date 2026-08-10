import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TELEGRAM_TOKEN, BOT_NAME, PORT, WEBHOOK_URL
from db import init_db
import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("reset", handlers.reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.chat))

    if WEBHOOK_URL:
        logger.info(f"{BOT_NAME} is starting (webhook mode) on port {PORT}...")
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}",
            allowed_updates=Update.ALL_TYPES,
        )
    else:
        logger.info(f"{BOT_NAME} is starting (polling mode)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()