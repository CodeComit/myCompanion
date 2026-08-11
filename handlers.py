"""
handlers.py — Telegram command and message handlers.
Each function here matches one user-facing interaction. bot.py just wires
these up to the Application; it doesn't contain any logic itself.
"""

import re
import time
import logging
from collections import defaultdict
from datetime import datetime

import dateparser
from dateparser.search import search_dates
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import BOT_NAME, RATE_LIMIT_SECONDS, OWNER_USER_ID, DEFAULT_TIMEZONE
from db import save_message, get_history, clear_history, add_scheduled_message
from gemini_client import generate_reply

logger = logging.getLogger(__name__)

# simple in-memory per-user cooldown to avoid spam / runaway API costs
_last_message_time: dict[int, float] = defaultdict(float)

# Only try to parse a time out of the message if it looks like a request
# to be messaged later — avoids misreading ordinary chat ("I woke up at 3")
# as a scheduling request.
_SCHEDULE_TRIGGER_RE = re.compile(
    r"\b(text|message|msg|ping|remind|wake|call)\s+me\b"
    r"|\bsend me a (message|text|reminder)\b",
    re.IGNORECASE,
)

_DATEPARSER_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "TIMEZONE": DEFAULT_TIMEZONE,
    "RETURN_AS_TIMEZONE_AWARE": True,
}


def _try_parse_schedule_request(text: str):
    """If the message looks like 'text me at 3' / 'remind me at 9pm
    tonight' / 'message me in 20 minutes', return the timezone-aware
    datetime it resolves to. Otherwise return None so the message falls
    through to a normal chat reply."""
    if not _SCHEDULE_TRIGGER_RE.search(text):
        return None
    try:
        results = search_dates(text, settings=_DATEPARSER_SETTINGS)
    except Exception:
        logger.exception("dateparser failed on: %r", text)
        return None
    if not results:
        return None
    # last date-like phrase in the message is usually the intended one
    # ("text me at 3" -> the "3" match)
    _, dt = results[-1]
    if dt <= datetime.now(dt.tzinfo):
        return None  # parsed to a time already in the past, ignore
    return dt


def _is_authorized(user_id: int) -> bool:
    """If OWNER_USER_ID is set in .env, only that Telegram user can use the
    bot. Leave OWNER_USER_ID unset to allow anyone to chat with it."""
    if OWNER_USER_ID is None:
        return True
    return user_id == OWNER_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        f"Hi, I'm {BOT_NAME} 💬\n\n"
        "Just talk to me like you would with a friend — I can chat in "
        "whatever language you like.\n\n"
        "Commands:\n"
        "/reset — clear our conversation history\n"
        "/help — show this message again"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update.effective_user.id):
        return
    clear_history(update.effective_user.id)
    await update.message.reply_text("Okay, clean slate! I've forgotten our previous chat. 🧹")


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _is_authorized(user_id):
        return  # silently ignore messages from anyone but the owner

    text = update.message.text

    # basic rate limiting per user
    now = time.time()
    if now - _last_message_time[user_id] < RATE_LIMIT_SECONDS:
        return
    _last_message_time[user_id] = now

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    scheduled_dt = _try_parse_schedule_request(text)
    if scheduled_dt:
        add_scheduled_message(user_id, scheduled_dt.timestamp(), note=text)
        save_message(user_id, "user", text)
        time_str = scheduled_dt.strftime("%-I:%M %p on %b %-d")
        confirm = f"got it, i'll text you at {time_str} 🤍"
        save_message(user_id, "model", confirm)
        await update.message.reply_text(confirm)
        return

    history = get_history(user_id)
    reply_text = generate_reply(history, text)

    save_message(user_id, "user", text)
    save_message(user_id, "model", reply_text)

    await update.message.reply_text(reply_text)