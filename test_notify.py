"""Gửi thử thông báo mẫu vào nhóm nhân sự để kiểm tra cấu hình.

Cách dùng:
  1. Điền TELEGRAM_BOT_TOKEN và TELEGRAM_ADMIN_CHAT_ID vào .env.
  2. Chạy:  python test_notify.py
  3. Kiểm tra nhóm nhân sự có nhận được 2 tin mẫu không.
"""
from __future__ import annotations

import asyncio

from app import notify
from app.config import settings


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("Chưa có TELEGRAM_BOT_TOKEN trong .env")
    if not settings.telegram_admin_chat_id:
        raise SystemExit("Chưa có TELEGRAM_ADMIN_CHAT_ID trong .env (chạy get_chat_id.py để lấy)")

    print("Đang gửi 2 thông báo mẫu vào nhóm nhân sự...")
    await notify.order_placed(
        channel="telegram",
        user_id="khach_test",
        message="Chốt 2 bộ đen size L. Nguyễn Văn A 0987654321, 12 Lê Lợi Q1",
        phone="0987654321",
    )
    await notify.hard_question(
        channel="telegram",
        user_id="khach_test",
        question="shop có ship qua Lào không?",
    )
    print("Xong. Kiểm tra nhóm nhân sự trên Telegram nhé.")


if __name__ == "__main__":
    asyncio.run(main())
