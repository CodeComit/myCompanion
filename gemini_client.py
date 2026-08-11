"""
gemini_client.py — thin wrapper around the Groq SDK.

Kept the filename as `gemini_client.py` (and the same function names/
signatures) on purpose, so nothing in bot.py or handlers.py has to change —
they just import generate_reply / generate_proactive_message from here.
"""

import logging
import random
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, PERSONA

logger = logging.getLogger(__name__)

_client = Groq(api_key=GROQ_API_KEY)

# Different "reasons" she might reach out first — one is picked at random
# each time so the proactive pings don't all sound the same ("how are you"
# every single time reads as a bot). Keep these as loose intents, not exact
# lines — the model still writes it in its own voice.
_PROACTIVE_THEMES = [
    "check in on how they're doing right now, casually",
    "ask if now's actually an okay time to talk / if they're busy",
    "share a small random thought or something mundane happening on your end",
    "bring up something specific they mentioned earlier and ask about it",
    "tease them lightly about something from your recent conversation",
    "just say you were thinking about them, no real reason",
    "ask what they're doing right this second",
    "ask how their day/night is going so far",
    "admit you're a little bored/tired and ask what they're up to",
]


def _to_groq_messages(history: list[dict]) -> list[dict]:
    """db.get_history() returns [{"role": "user"/"model", "parts": [text]}, ...]
    (that shape came from the old Gemini SDK). Groq/OpenAI-style chat
    completions want [{"role": "user"/"assistant", "content": text}, ...],
    so translate it here — db.py doesn't need to change."""
    messages = [{"role": "system", "content": PERSONA}]
    for turn in history:
        role = "assistant" if turn["role"] == "model" else "user"
        content = turn["parts"][0] if turn.get("parts") else ""
        messages.append({"role": role, "content": content})
    return messages


def generate_reply(history: list[dict], user_message: str) -> str:
    try:
        messages = _to_groq_messages(history)
        messages.append({"role": "user", "content": user_message})
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Groq API error")
        return "Sorry, I hit a little glitch just now — could you say that again?"


def generate_proactive_message(history: list[dict]):
    """Ask the model to reach out FIRST, as if she initiated contact after
    time apart — not a reply to anything the user said. Returns None on
    failure so the caller can skip sending rather than surface an error."""
    try:
        messages = _to_groq_messages(history)
        theme = random.choice(_PROACTIVE_THEMES)
        trigger = (
            "[Some time has passed since you last talked. Reach out to them "
            "first, unprompted — like you were thinking about them. Right "
            f"now, specifically: {theme}. Keep it to ONE short, natural "
            "text — one sentence or less, the way a real text actually "
            "looks, not a full message. Don't explain yourself or write "
            "more than that.]"
        )
        messages.append({"role": "user", "content": trigger})
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=1.0,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Groq API error (proactive message)")
        return None