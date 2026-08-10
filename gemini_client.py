"""
gemini_client.py — thin wrapper around the Gemini SDK.
"""

import logging
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, PERSONA

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=PERSONA)


def generate_reply(history: list[dict], user_message: str) -> str:
    try:
        chat_session = _model.start_chat(history=history)
        response = chat_session.send_message(user_message)
        return response.text.strip()
    except Exception:
        logger.exception("Gemini API error")
        return "Sorry, I hit a little glitch just now — could you say that again?"


def generate_proactive_message(history: list[dict]):
    """Ask the model to reach out FIRST, as if she initiated contact after
    time apart — not a reply to anything the user said. Returns None on
    failure so the caller can skip sending rather than surface an error."""
    try:
        chat_session = _model.start_chat(history=history)
        trigger = (
            "[Some hours have passed since you last talked. Reach out to "
            "them first, unprompted — like you were thinking about them. "
            "Keep it short, warm, and natural. Reference something from "
            "your recent conversation if it fits, or just ask how their "
            "day's going / what they're up to.]"
        )
        response = chat_session.send_message(trigger)
        return response.text.strip()
    except Exception:
        logger.exception("Gemini API error (proactive message)")
        return None