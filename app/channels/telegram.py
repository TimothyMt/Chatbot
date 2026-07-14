"""Tích hợp Telegram: gửi tin nhắn, gửi ảnh, long-polling để test."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class TgMessage:
    chat_id: str
    text: str
    chat_type: str  # "private" (khách) / "group" / "supergroup" (nhân sự) / ...
    reply_to_text: str = ""  # nội dung tin được reply (dùng cho nhân viên trả lời khách)


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


def extract_messages(update: dict) -> list[TgMessage]:
    """Rút thông tin tin nhắn từ một update webhook của Telegram."""
    out: list[TgMessage] = []
    msg = update.get("message") or update.get("edited_message")
    if msg:
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        text = msg.get("text")
        if chat_id and text:
            reply_to = (msg.get("reply_to_message") or {}).get("text", "")
            out.append(
                TgMessage(
                    chat_id=str(chat_id),
                    text=text,
                    chat_type=chat.get("type", ""),
                    reply_to_text=reply_to,
                )
            )
    return out


def parse_customer_from_alert(alert_text: str) -> str | None:
    """Từ tin thông báo (mà nhân viên reply vào), lấy chat_id của khách Telegram."""
    import re

    if "Kênh: telegram" not in alert_text:
        return None
    m = re.search(r"Khách:\s*(-?\d+)", alert_text)
    return m.group(1) if m else None
