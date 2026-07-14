"""Tích hợp Facebook Messenger (webhook + gửi tin nhắn)."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/v21.0/me/messages"


def verify(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Xác thực webhook khi Facebook gọi GET để verify."""
    if mode == "subscribe" and token == settings.fb_verify_token:
        return challenge
    return None


async def send_message(recipient_id: str, text: str) -> None:
    if not settings.fb_page_access_token:
        logger.warning("Chưa cấu hình FB_PAGE_ACCESS_TOKEN, bỏ qua gửi tin.")
        return
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            GRAPH_URL,
            params={"access_token": settings.fb_page_access_token},
            json=payload,
        )
        if resp.status_code >= 400:
            logger.error("Gửi Messenger lỗi %s: %s", resp.status_code, resp.text)


async def send_image(recipient_id: str, image_url: str, caption: str = "") -> None:
    if not settings.fb_page_access_token or not image_url:
        return
    if caption:
        await send_message(recipient_id, caption)
    payload = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True},
            }
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            GRAPH_URL,
            params={"access_token": settings.fb_page_access_token},
            json=payload,
        )
        if resp.status_code >= 400:
            logger.error("Gửi ảnh Messenger lỗi %s: %s", resp.status_code, resp.text)


def extract_messages(body: dict) -> list[tuple[str, str]]:
    """Rút (sender_id, text) từ payload webhook của Messenger."""
    out: list[tuple[str, str]] = []
    for entry in body.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")
            # Bỏ qua tin echo do chính page gửi.
            if sender and text and not message.get("is_echo"):
                out.append((sender, text))
    return out
