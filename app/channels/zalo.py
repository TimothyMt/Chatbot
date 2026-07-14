"""Tích hợp Zalo Official Account (webhook + gửi tin nhắn)."""
from __future__ import annotations

import logging

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

ZALO_SEND_URL = "https://openapi.zalo.me/v3.0/oa/message/cs"


async def send_message(user_id: str, text: str) -> None:
    if not settings.zalo_oa_access_token:
        logger.warning("Chưa cấu hình ZALO_OA_ACCESS_TOKEN, bỏ qua gửi tin.")
        return
    payload = {
        "recipient": {"user_id": user_id},
        "message": {"text": text},
    }
    headers = {"access_token": settings.zalo_oa_access_token}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(ZALO_SEND_URL, json=payload, headers=headers)
        if resp.status_code >= 400 or resp.json().get("error", 0) != 0:
            logger.error("Gửi Zalo lỗi %s: %s", resp.status_code, resp.text)


async def send_image(user_id: str, image_url: str, caption: str = "") -> None:
    if not settings.zalo_oa_access_token or not image_url:
        return
    payload = {
        "recipient": {"user_id": user_id},
        "message": {
            "text": caption or " ",
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "media",
                    "elements": [{"media_type": "image", "url": image_url}],
                },
            },
        },
    }
    headers = {"access_token": settings.zalo_oa_access_token}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(ZALO_SEND_URL, json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Gửi ảnh Zalo lỗi %s: %s", resp.status_code, resp.text)


def extract_messages(body: dict) -> list[tuple[str, str]]:
    """Rút (user_id, text) từ payload webhook của Zalo OA."""
    out: list[tuple[str, str]] = []
    if body.get("event_name") == "user_send_text":
        user_id = body.get("sender", {}).get("id")
        text = body.get("message", {}).get("text")
        if user_id and text:
            out.append((user_id, text))
    return out
