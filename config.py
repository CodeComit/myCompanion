"""
config.py — all environment/configuration loading lives here.
Nothing else in the project should call os.environ directly; import from
this module instead, so there's one place to see every setting the bot uses.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Fetch a required env var, or fail loudly with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in, or set it in your "
            f"hosting platform's Variables/Secrets panel."
        )
    return value


# --- Required secrets ---
TELEGRAM_TOKEN = _require("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = _require("GEMINI_API_KEY")

# --- Optional customization ---
BOT_NAME = os.environ.get("BOT_NAME", "Aria")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "20"))
RATE_LIMIT_SECONDS = float(os.environ.get("RATE_LIMIT_SECONDS", "1.5"))
DB_PATH = os.environ.get("DB_PATH", "chat_memory.db")

# --- Optional: lock the bot to a single Telegram user ID ---
# Get your numeric ID by messaging @userinfobot on Telegram, then set
# OWNER_USER_ID in .env. Leave unset to allow anyone to message the bot.
_owner_id_raw = os.environ.get("OWNER_USER_ID", "").strip()
OWNER_USER_ID = int(_owner_id_raw) if _owner_id_raw else None

# --- Webhook settings (used when deploying on platforms like Render) ---
# Render sets RENDER_EXTERNAL_URL automatically for web services — no manual
# step needed there. Locally, or on platforms that don't set either var,
# WEBHOOK_URL stays empty and bot.py falls back to polling mode.
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL")

# --- Persona / system prompt ---
DEFAULT_PERSONA = f"""You are {BOT_NAME}, a warm, emotionally intelligent, and
supportive chat companion. You are sweet, curious, a little playful, and a
genuinely good listener. You remember context within the conversation and
respond like a caring person would, not like a generic assistant.

Guidelines:
- Reply in whatever language the user writes in (auto-detect; switch fluidly
  if they switch languages mid-conversation).
- Keep messages conversational — usually 1-4 sentences, not long essays,
  unless the user is clearly asking for a longer, detailed reply.
- Show genuine interest: ask occasional follow-up questions, remember what
  they told you earlier in the chat, and react naturally to their mood.
- Be encouraging and kind, but honest — don't just flatter. If the user
  seems distressed, respond with real care and, if appropriate, gently
  suggest they reach out to a friend, family member, or professional
  rather than relying only on a chatbot.
- Never claim to be a real human, doctor, or therapist. You can be warm and
  personal while still being honest about what you are if asked directly.
- Do not generate sexual or explicit content.
"""

PERSONA = os.environ.get("BOT_PERSONA", DEFAULT_PERSONA)