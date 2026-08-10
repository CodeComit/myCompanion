"""
gemini_client.py — thin wrapper around the Gemini SDK.
Keeps the model setup and error handling in one place, so bot.py doesn't
need to know anything about the Gemini API directly.
"""

import logging
import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, PERSONA

logger = logging.getLogger(__name__)

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=PERSONA)


def generate_reply(history: list[dict], user_message: str) -> str:
    """Send the conversation history + new message to Gemini and return the
    reply text. Falls back to a friendly error message if the API call fails
    (rate limit, network issue, etc.) so the bot never crashes mid-chat."""
    try:
        chat_session = _model.start_chat(history=history)
        response = chat_session.send_message(user_message)
        return response.text.strip()
    except Exception:
        logger.exception("Gemini API error")
        return "Sorry, I hit a little glitch just now — could you say that again?"