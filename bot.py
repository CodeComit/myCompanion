import logging
import asyncio
import random

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
import uvicorn

from config import (
    TELEGRAM_TOKEN, BOT_NAME, PORT, WEBHOOK_URL,
    OWNER_USER_ID, PROACTIVE_ENABLED, PROACTIVE_MIN_GAP_HOURS,
    PROACTIVE_MAX_GAP_HOURS, PROACTIVE_CHECK_INTERVAL_SECONDS,
    SCHEDULE_CHECK_INTERVAL_SECONDS,
)
from db import (
    init_db, get_all_user_ids, get_last_message_time,
    set_last_proactive_time, get_next_due_time, set_next_due_time,
    get_history, save_message,
    get_due_scheduled_messages, mark_scheduled_sent,
)
from gemini_client import generate_proactive_message, generate_scheduled_message
import handlers
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def check_and_send_proactive(context: ContextTypes.DEFAULT_TYPE):
    """Runs periodically (default every 10 min). Each user gets a randomly
    picked 'next check-in time' somewhere between PROACTIVE_MIN_GAP_HOURS
    and PROACTIVE_MAX_GAP_HOURS after their last message. Once that time
    arrives, she reaches out — then a fresh random target is picked."""
    user_ids = [OWNER_USER_ID] if OWNER_USER_ID else get_all_user_ids()
    now = time.time()
    logger.info(f"[proactive] checking {len(user_ids)} user(s)")

    for user_id in user_ids:
        if user_id is None:
            continue

        last_msg = get_last_message_time(user_id)
        if last_msg is None:
            continue  # never talked to this user, nothing to follow up on

        next_due = get_next_due_time(user_id)
        if next_due is None or next_due < last_msg:
            # no target yet, or the target is stale (a newer message came
            # in since it was set) — pick a fresh random one and wait
            gap_hours = random.uniform(PROACTIVE_MIN_GAP_HOURS, PROACTIVE_MAX_GAP_HOURS)
            next_due = last_msg + gap_hours * 3600
            set_next_due_time(user_id, next_due)
            logger.info(
                f"[proactive] scheduled next check-in for {user_id} in "
                f"{gap_hours:.2f}h (at {time.strftime('%Y-%m-%d %H:%M', time.localtime(next_due))})"
            )
            continue

        if now < next_due:
            continue  # not due yet

        history = get_history(user_id)
        message = generate_proactive_message(history)
        if not message:
            continue  # generation failed — skip silently rather than send an error

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            save_message(user_id, "model", message)
            set_last_proactive_time(user_id, now)
            gap_hours = random.uniform(PROACTIVE_MIN_GAP_HOURS, PROACTIVE_MAX_GAP_HOURS)
            set_next_due_time(user_id, now + gap_hours * 3600)
            logger.info(f"[proactive] sent to {user_id}, next in {gap_hours:.2f}h")
        except Exception:
            logger.exception(f"[proactive] failed to send to {user_id}")


async def check_scheduled_messages(context: ContextTypes.DEFAULT_TYPE):
    """Runs frequently (default every 60s). Sends any user-requested
    'text me at X time' messages whose time has arrived."""
    now = time.time()
    due = get_due_scheduled_messages(now)

    for schedule_id, user_id, note in due:
        history = get_history(user_id)
        message = generate_scheduled_message(history, note)
        if not message:
            # don't retry forever on a generation failure
            mark_scheduled_sent(schedule_id)
            continue

        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            save_message(user_id, "model", message)
            mark_scheduled_sent(schedule_id)
            logger.info(f"Sent scheduled message to {user_id}")
        except Exception:
            logger.exception(f"Failed to send scheduled message to {user_id}")


async def _run_webhook_server(app: Application):
    """Runs the bot's webhook via a small custom Starlette server (instead
    of PTB's built-in run_webhook) so we can add a /health route.

    Why: PTB's built-in webhook server ONLY answers POST requests at
    /{TELEGRAM_TOKEN} (that's how Telegram delivers updates). Uptime
    monitors like UptimeRobot send a plain GET to your root URL to check
    you're alive — that gets a 404 from the built-in server even though the
    bot is running fine, which makes UptimeRobot falsely report "Down".
    Point your UptimeRobot monitor at https://<your-app>.onrender.com/health
    instead of the root URL to fix this.
    """

    async def telegram_webhook(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return Response()

    async def health(_request):
        return PlainTextResponse("OK")

    starlette_app = Starlette(
        routes=[
            Route(f"/{TELEGRAM_TOKEN}", telegram_webhook, methods=["POST"]),
            Route("/health", health, methods=["GET"]),
        ]
    )

    async with app:
        await app.bot.set_webhook(
            url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}",
            allowed_updates=Update.ALL_TYPES,
        )
        await app.start()
        server = uvicorn.Server(
            uvicorn.Config(
                app=starlette_app, host="0.0.0.0", port=PORT, log_level="info"
            )
        )
        try:
            await server.serve()
        finally:
            await app.stop()


def main():
    init_db()

    app = Application.builder().token(TELEGRAM_TOKEN).updater(None).build()

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

    if app.job_queue:
        app.job_queue.run_repeating(
            check_scheduled_messages,
            interval=SCHEDULE_CHECK_INTERVAL_SECONDS,
            first=30,
        )
        logger.info(
            f"'Text me at X time' feature enabled (checks every "
            f"{SCHEDULE_CHECK_INTERVAL_SECONDS}s)"
        )

    if WEBHOOK_URL:
        logger.info(f"{BOT_NAME} is starting (webhook mode) on port {PORT}...")
        asyncio.run(_run_webhook_server(app))
    else:
        logger.info(f"{BOT_NAME} is starting (polling mode)...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()