"""Gọi Telegram Bot API (gửi tin, ảnh, nút bấm duyệt...)."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


async def _call(method: str, payload: dict) -> dict | None:
    if not settings.telegram_bot_token:
        logger.warning("Thiếu TELEGRAM_BOT_TOKEN, bỏ qua %s", method)
        return None
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(_url(method), json=payload)
    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code >= 400 or not data.get("ok", False):
        logger.error("Telegram %s lỗi %s: %s", method, resp.status_code, resp.text[:300])
        return None
    return data.get("result")


async def send_message(
    chat_id: str | int,
    text: str,
    reply_markup: dict | None = None,
) -> dict | None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _call("sendMessage", payload)


async def send_photo(
    chat_id: str | int, photo: str, caption: str = ""
) -> dict | None:
    """photo: URL công khai hoặc telegram file_id."""
    return await _call(
        "sendPhoto", {"chat_id": chat_id, "photo": photo, "caption": caption}
    )


async def answer_callback(callback_id: str, text: str = "") -> None:
    await _call("answerCallbackQuery", {"callback_query_id": callback_id, "text": text})


async def edit_message_text(
    chat_id: str | int, message_id: int, text: str
) -> None:
    await _call(
        "editMessageText",
        {"chat_id": chat_id, "message_id": message_id, "text": text},
    )


def approval_keyboard(teaching_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Duyệt", "callback_data": f"teach:ok:{teaching_id}"},
                {"text": "❌ Bỏ", "callback_data": f"teach:no:{teaching_id}"},
            ]
        ]
    }
