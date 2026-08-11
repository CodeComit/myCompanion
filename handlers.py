"""
handlers.py — Telegram command and message handlers.
Each function here matches one user-facing interaction. bot.py just wires
these up to the Application; it doesn't contain any logic itself.
"""

import re
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import BOT_NAME, RATE_LIMIT_SECONDS, OWNER_USER_ID, DEFAULT_TIMEZONE
from db import save_message, get_history, clear_history, add_scheduled_message
from gemini_client import generate_reply

logger = logging.getLogger(__name__)

# simple in-memory per-user cooldown to avoid spam / runaway API costs
_last_message_time: dict[int, float] = defaultdict(float)

_TZ = ZoneInfo(DEFAULT_TIMEZONE)

# Only try to parse a time out of the message if it looks like a request
# to be messaged later — avoids misreading ordinary chat ("I woke up at 3")
# as a scheduling request.
_SCHEDULE_TRIGGER_RE = re.compile(
    r"\b(text|message|msg|ping|remind|wake|call)\s+me\b"
    r"|\bsend me a (message|text|reminder)\b",
    re.IGNORECASE,
)

# "in 20 minutes", "in 2 hours"
_RELATIVE_RE = re.compile(
    r"\bin\s+(\d+)\s*(minute|min|hour|hr)s?\b", re.IGNORECASE
)

# "at 2:35", "at 2:35pm", "at 9 am", "at 21:00"
_CLOCK_TIME_RE = re.compile(
    r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.IGNORECASE
)


def _resolve_clock_time(now: datetime, hour: int, minute: int, meridiem: str | None, night: bool):
    """Turn an hour/minute (possibly ambiguous, e.g. '2:35' with no am/pm)
    into a concrete future datetime — always the NEXT real occurrence,
    never a random/far-off date."""
    if meridiem:
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour != 12:
            hour = (hour % 12) + 12
        elif meridiem == "am" and hour == 12:
            hour = 0
        candidates = [now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)]
    elif night and 1 <= hour <= 11:
        # "tonight at 9" -> clearly PM even without saying so
        candidates = [now.replace(hour=hour + 12, minute=minute, second=0, microsecond=0)]
    elif 1 <= hour <= 12:
        # genuinely ambiguous ("at 2:35") — consider both AM and PM, and
        # pick whichever is soonest without being in the past
        h_am = hour % 12
        h_pm = (hour % 12) + 12
        candidates = [
            now.replace(hour=h_am, minute=minute, second=0, microsecond=0),
            now.replace(hour=h_pm, minute=minute, second=0, microsecond=0),
        ]
    else:
        # 0 or 13-23 -> unambiguous 24-hour value
        candidates = [now.replace(hour=hour % 24, minute=minute, second=0, microsecond=0)]

    future = [c for c in candidates if c > now]
    if future:
        return min(future)
    # every candidate for "today" has already passed -> next day
    return min(candidates) + timedelta(days=1)


def _try_parse_schedule_request(text: str):
    """If the message looks like 'text me at 3' / 'remind me at 9pm
    tonight' / 'message me in 20 minutes', return the datetime it resolves
    to (always in the future, always the next real occurrence). Otherwise
    return None so the message falls through to a normal chat reply."""
    if not _SCHEDULE_TRIGGER_RE.search(text):
        return None

    now = datetime.now(_TZ)

    m = _RELATIVE_RE.search(text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(minutes=amount) if unit.startswith("min") else timedelta(hours=amount)
        return now + delta

    m = _CLOCK_TIME_RE.search(text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        meridiem = m.group(3)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        night = bool(re.search(r"\btonight\b", text, re.IGNORECASE))
        return _resolve_clock_time(now, hour, minute, meridiem, night)

    return None  # trigger phrase present but no recognizable time -> just chat normally


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