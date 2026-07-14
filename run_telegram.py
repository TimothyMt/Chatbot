"""Bot Telegram để TEST — chạy bằng long-polling, không cần domain/HTTPS.

Cách dùng:
  1. Nhắn @BotFather trên Telegram -> /newbot -> lấy TELEGRAM_BOT_TOKEN.
  2. Điền TELEGRAM_BOT_TOKEN vào .env.
  3. (Thông báo nhân viên) Tạo 1 nhóm Telegram, thêm bot vào, gửi 1 tin trong
     nhóm; log dưới đây sẽ in ra chat_id của nhóm -> điền vào TELEGRAM_ADMIN_CHAT_ID.
  4. Chạy:  python run_telegram.py   rồi nhắn cho bot để test.
"""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.channels import telegram
from app.config import settings
from app.knowledge import knowledge_base
from app.pipeline import process_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-bot")


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("Chưa có TELEGRAM_BOT_TOKEN trong .env")

    count = knowledge_base.reload()
    logger.info("Đã nạp %d câu Q&A. Bot Telegram đang chạy (Ctrl+C để dừng)...", count)

    offset = 0
    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=40) as client:
        while True:
            try:
                resp = await client.get(
                    f"{base}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Lỗi getUpdates (%s), thử lại sau 3s.", exc)
                await asyncio.sleep(3)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                for m in telegram.extract_messages(update):
                    logger.info("Tin từ %s chat_id=%s: %r", m.chat_type, m.chat_id, m.text)
                    if m.chat_type == "private":
                        reply = await process_message("telegram", m.chat_id, m.text)
                        if reply.text.strip():
                            await telegram.send_message(m.chat_id, reply.text)
                        for url, caption in reply.images:
                            await telegram.send_photo(m.chat_id, url, caption)
                    elif m.chat_id == settings.telegram_admin_chat_id and m.reply_to_text:
                        # Nhân viên reply thông báo -> chuyển lời tới khách.
                        customer_id = telegram.parse_customer_from_alert(m.reply_to_text)
                        if customer_id:
                            await telegram.send_message(customer_id, m.text)
                            await telegram.send_message(
                                m.chat_id, f"✅ Đã gửi tới khách {customer_id}."
                            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
