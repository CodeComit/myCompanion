import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from config import (
    TELEGRAM_TOKEN, BOT_NAME, PORT, WEBHOOK_URL,
    OWNER_USER_ID, PROACTIVE_ENABLED, PROACTIVE_MIN_GAP_HOURS,
    PROACTIVE_CHECK_INTERVAL_SECONDS,
)
from db import (
    init_db, get_all_user_ids, get_last_message_time,
    get_last_proactive_time, set_last_proactive_time, get_history, save_message,
)
from gemini_client import generate_proactive_message
import handlers
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def check_and_send_proactive(context: ContextTypes.DEFAULT_TYPE):
    """Runs periodically. If it's been long enough since a user last
    messaged (and long enough since she last reached out to them), send an
    unprompted, in-character message."""
    user_ids = [OWNER_USER_ID] if OWNER_USER_ID else get_all_user_ids()
    now = time.time()

    for user_id in user_ids:
        if user_id is None:
            continue

        last_msg = get_last_message_time(user_id)
        if last_msg is None:
            continue  # never talked to this user, nothing to follow up on

        gap_hours = (now - last_msg) / 3600
        if gap_hours < PROACTIVE_MIN_GAP_HOURS:
            continue

        last_proactive = get_last_proactive_time(user_id)
        if last_proactive and (now - last_proactive) / 3600 < PROACTIVE_MIN_GAP_HOURS:
            continue  # already reached out recently, don't spam

        history = get_history(user_id)
        message = generate_proactive_message(history)
        if not message:
            continue  # generation failed — skip silently rather than send an error

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            save_message(user_id, "model", message)
            set_last_proactive_time(user_id, now)
            logger.info(f"Sent proactive message to {user_id}")
        except Exception:
            logger.exception(f"Failed to send proactive message to {user_id}")


def main():
    init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("reset", handlers.reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.chat))

    if PROACTIVE_ENABLED and app.job_queue:
        app.job_queue.run_repeating(
            check_and_send_proactive,
            interval=PROACTIVE_CHECK_INTERVAL_SECONDS,
            first=60,
        )
        logger.info(
            f"Proactive messaging enabled (checks every "
            f"{PROACTIVE_CHECK_INTERVAL_SECONDS}s, min gap "
            f"{PROACTIVE_MIN_GAP_HOURS}h)"
        )
    elif PROACTIVE_ENABLED:
        logger.warning(
            "PROACTIVE_ENABLED is true but job_queue is unavailable — "
            "check that requirements.txt includes the [job-queue] extra."
        )

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