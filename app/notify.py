"""Kênh thông báo nội bộ cho nhân viên (qua Telegram).

Gửi cảnh báo tới nhóm/chat có id = TELEGRAM_ADMIN_CHAT_ID khi:
  - Khách để lại thông tin đặt hàng (chốt đơn)
  - Bot gặp câu hỏi khó không trả lời được
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .channels import telegram
from .config import settings

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _now() -> str:
    return datetime.now(_TZ).strftime("%H:%M %d/%m/%Y")


async def _send_admin(text: str) -> None:
    if not settings.telegram_admin_chat_id:
        logger.info("Chưa cấu hình TELEGRAM_ADMIN_CHAT_ID, bỏ qua thông báo.")
        return
    await telegram.send_message(settings.telegram_admin_chat_id, text)


async def order_placed(channel: str, user_id: str, message: str, phone: str) -> None:
    await _send_admin(
        "🛒 CHỐT ĐƠN - khách để lại thông tin\n"
        f"• Thời gian: {_now()}\n"
        f"• Kênh: {channel}\n"
        f"• Khách: {user_id}\n"
        f"• SĐT: {phone}\n"
        f"• Nội dung: {message}"
    )


async def hard_question(channel: str, user_id: str, question: str) -> None:
    await _send_admin(
        "❓ CÂU HỎI KHÓ - bot chưa trả lời được\n"
        f"• Thời gian: {_now()}\n"
        f"• Kênh: {channel}\n"
        f"• Khách: {user_id}\n"
        f"• Câu hỏi: {question}"
    )
