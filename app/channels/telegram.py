"""Tích hợp Telegram: gửi tin nhắn, gửi ảnh, long-polling để test."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


async def send_message(chat_id: str | int, text: str) -> None:
    if not settings.telegram_bot_token:
        logger.warning("Chưa cấu hình TELEGRAM_BOT_TOKEN, bỏ qua gửi tin.")
        return
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _api("sendMessage"),
            json={"chat_id": chat_id, "text": text},
        )
        if resp.status_code >= 400:
            logger.error("Gửi Telegram lỗi %s: %s", resp.status_code, resp.text)


async def send_photo(chat_id: str | int, image_url: str, caption: str = "") -> None:
    if not settings.telegram_bot_token or not image_url:
        return
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            _api("sendPhoto"),
            json={"chat_id": chat_id, "photo": image_url, "caption": caption},
        )
        if resp.status_code >= 400:
            logger.error("Gửi ảnh Telegram lỗi %s: %s", resp.status_code, resp.text)


def extract_messages(update: dict) -> list[tuple[str, str, str]]:
    """Rút (chat_id, text, chat_type) từ một update webhook của Telegram.

    chat_type: "private" (chat riêng của khách) / "group" / "supergroup" / ...
    """
    out: list[tuple[str, str, str]] = []
    msg = update.get("message") or update.get("edited_message")
    if msg:
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text")
        if chat_id and text:
            out.append((str(chat_id), text, chat.get("type", "")))
    return out
