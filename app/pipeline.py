"""Luồng xử lý chung cho mọi kênh (Telegram/Messenger/Zalo).

process_message() nhận tin nhắn của khách và trả về:
  - reply : câu trả lời văn bản
  - images: danh sách (url, caption) ảnh cần gửi kèm
Đồng thời tự bắn thông báo cho nhân viên khi:
  - khách để lại thông tin đặt hàng (có số điện thoại) -> chốt đơn
  - bot không trả lời được -> câu hỏi khó
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import notify
from .images import image_library
from .responder import answer_with_meta

# SĐT Việt Nam: bắt đầu 0, 10 số (có thể có khoảng trắng/dấu chấm giữa các cụm).
_PHONE_RE = re.compile(r"(0\d{2}[\s.]?\d{3}[\s.]?\d{3,4})")

# Từ khoá cho thấy khách đang cung cấp thông tin nhận hàng.
_ORDER_HINTS = ("địa chỉ", "nhận hàng", "lên đơn", "đặt", "ship về", "gửi về", "sđt", "số nhà")


@dataclass
class Reply:
    text: str
    images: list[tuple[str, str]] = field(default_factory=list)
    source: str = ""


def _extract_phone(text: str) -> str | None:
    m = _PHONE_RE.search(text)
    return m.group(1) if m else None


def _looks_like_order(text: str, phone: str | None) -> bool:
    # Có SĐT + (địa chỉ dài hoặc từ khoá đặt hàng) -> coi như thông tin đặt hàng.
    if not phone:
        return False
    low = text.lower()
    if any(h in low for h in _ORDER_HINTS):
        return True
    # Tin nhắn dài kèm SĐT thường là "SĐT + địa chỉ".
    return len(text) >= 25


async def process_message(channel: str, user_id: str, text: str) -> Reply:
    meta = answer_with_meta(text)
    reply = Reply(text=meta["reply"], source=meta["source"])
    is_fallback = meta["source"] in {"fallback", "fallback-ai"}

    phone = _extract_phone(text)
    is_order = _looks_like_order(text, phone)

    # Ảnh: gửi kèm khi khách hỏi về bảng size / mẫu / màu / STK...
    # (bỏ qua nếu khách đang gửi thông tin đặt hàng để tránh gửi ảnh thừa)
    matched_images = [] if is_order else image_library.match(text)
    reply.images = [(r.url, r.caption) for r in matched_images]

    answered_by_image = is_fallback and bool(matched_images)

    # Câu khó (bot không biết): KHÔNG trả lời khách, để nhân viên tự xử lý.
    # (Nếu đã có ảnh + chú thích trả lời thay thì vẫn gửi ảnh.)
    if is_fallback:
        reply.text = ""

    # Thông báo: chốt đơn.
    if is_order:
        await notify.order_placed(channel, user_id, text, phone or "")

    # Thông báo: câu hỏi khó (chỉ khi thực sự không trả lời được, kể cả bằng ảnh).
    if is_fallback and not answered_by_image:
        await notify.hard_question(channel, user_id, text)

    return reply
