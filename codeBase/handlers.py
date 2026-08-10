"""
handlers.py — Telegram command and message handlers.
Each function here matches one user-facing interaction. bot.py just wires
these up to the Application; it doesn't contain any logic itself.
"""

import time
import logging
from collections import defaultdict

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config import BOT_NAME, RATE_LIMIT_SECONDS, OWNER_USER_ID
from db import save_message, get_history, clear_history
from gemini_client import generate_reply

logger = logging.getLogger(__name__)

# simple in-memory per-user cooldown to avoid spam / runaway API costs
_last_message_time: dict[int, float] = defaultdict(float)


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

    history = get_history(user_id)
    reply_text = generate_reply(history, text)

    save_message(user_id, "user", text)
    save_message(user_id, "model", reply_text)

    await update.message.reply_text(reply_text)