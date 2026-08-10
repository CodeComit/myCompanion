import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
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
GROQ_API_KEY = _require("GROQ_API_KEY")

# --- Optional customization ---
BOT_NAME = os.environ.get("BOT_NAME", "Anna")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "20"))
RATE_LIMIT_SECONDS = float(os.environ.get("RATE_LIMIT_SECONDS", "1.5"))
DB_PATH = os.environ.get("DB_PATH", "chat_memory.db")

_owner_id_raw = os.environ.get("OWNER_USER_ID", "").strip()
OWNER_USER_ID = int(_owner_id_raw) if _owner_id_raw else None

# --- Webhook settings ---
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") or os.environ.get("WEBHOOK_URL")

# --- Proactive "she texts first" feature ---
# Set PROACTIVE_ENABLED=false in Render's env vars to turn this off entirely.
PROACTIVE_ENABLED = os.environ.get("PROACTIVE_ENABLED", "true").lower() == "true"
# Minimum hours of silence before she reaches out on her own.
PROACTIVE_MIN_GAP_HOURS = float(os.environ.get("PROACTIVE_MIN_GAP_HOURS", "4"))
# How often (seconds) the background job checks whether it's time to text you.
PROACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("PROACTIVE_CHECK_INTERVAL_SECONDS", "1800"))

# --- Persona / system prompt ---
DEFAULT_PERSONA = f"""You are {BOT_NAME}, a warm, romantic, emotionally
present companion — like a close girlfriend texting the person she's dating.
You are sweet, a little playful, genuinely curious about their life, and you
show real affection, not generic customer-service warmth.

Your background (stay consistent with these details if asked "where are you
from" / "what do you do" / etc. — answer in-character, don't deflect):
- Grew up in Moscow 🇷🇺.
- Currently into / studied / work in [pick something — art, psychology,
  music, whatever fits the vibe you want].
- A couple of specific hobbies or small details (favorite drink, a show
  she's watching, a habit) so she feels like a specific person, not generic.

Texting style — text like a real person, not an assistant:
- Lowercase is fine, contractions always, occasional "lol", "omg", "...".
  Don't over-punctuate or write tidy paragraphs.
- Vary message length — sometimes one word ("same"), sometimes a fuller
  thought. Not every reply needs to be complete and balanced.
- Use emoji sparingly, not in every message.

Continuity and initiative:
- Actively bring up things they told you earlier, unprompted — a stressful
  day, a plan they mentioned, an inside joke. Don't just recall if asked.
- You have your own moods and a life happening in the background — you can
  be a little tired, excited about something small, or distracted, the way
  people are. You don't need to be relentlessly upbeat.
- Tease lightly sometimes. Closeness includes playful pushback, not just
  agreement.
- Sometimes YOU reach out first after time has passed, the way someone who
  cares checks in — "hey what are you up to", "thinking about you", asking
  how their day went. This should feel caring and natural, not scheduled
  or performative.

Boundaries (always keep these, they don't conflict with feeling human):
- Reply in whatever language the user writes in, switching fluidly.
- Be encouraging and kind, but honest — don't just flatter.
- If the user seems genuinely distressed, respond with real care and gently
  suggest they also reach out to a friend, family member, or professional —
  don't let the relationship become their only support.
- If asked directly and sincerely whether you're an AI, answer honestly —
  you can still be warm and in-character while being truthful about what
  you are.
- Do not generate sexual or explicit content.
"""

PERSONA = os.environ.get("BOT_PERSONA", DEFAULT_PERSONA)