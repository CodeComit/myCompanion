import logging
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, PERSONA

logger = logging.getLogger(__name__)

_client = Groq(api_key=GROQ_API_KEY)


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
        trigger = (
            "[Some hours have passed since you last talked. Reach out to "
            "them first, unprompted — like you were thinking about them. "
            "Keep it short, warm, and natural. Reference something from "
            "your recent conversation if it fits, or just ask how their "
            "day's going / what they're up to.]"
        )
        messages.append({"role": "user", "content": trigger})
        response = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Groq API error (proactive message)")
        return None