"""Lấy chat_id (dùng để cấu hình nhóm thông báo nhân sự).

Cách dùng:
  1. Điền TELEGRAM_BOT_TOKEN vào .env.
  2. Tạo 1 nhóm Telegram cho nhân sự, THÊM BOT VÀO NHÓM.
     (Với nhóm, vào cài đặt bot ở @BotFather -> /setprivacy -> Disable, để bot
      đọc được tin nhắn trong nhóm.)
  3. Gửi 1 tin bất kỳ trong nhóm (vd: "test").
  4. Chạy:  python get_chat_id.py
     Script sẽ in ra tên nhóm/chat kèm chat_id. Nhóm thường có id âm (vd -100...).
  5. Copy id của nhóm nhân sự vào TELEGRAM_ADMIN_CHAT_ID trong .env.
"""
from __future__ import annotations

import httpx

from app.config import settings


def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("Chưa có TELEGRAM_BOT_TOKEN trong .env")

    base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    resp = httpx.get(f"{base}/getUpdates", timeout=30)
    data = resp.json()
    results = data.get("result", [])

    if not results:
        print(
            "Chưa thấy tin nhắn nào. Hãy gửi 1 tin cho bot / trong nhóm có bot,\n"
            "rồi chạy lại script này. (Lưu ý bật quyền đọc tin nhóm ở @BotFather)."
        )
        return

    seen: dict[str, str] = {}
    for update in results:
        msg = update.get("message") or update.get("edited_message") or {}
        chat = msg.get("chat", {})
        cid = chat.get("id")
        if cid is None:
            continue
        name = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
        seen[str(cid)] = f"{chat.get('type', '?')} - {name}"

    print("Các chat đã thấy:")
    for cid, label in seen.items():
        print(f"  chat_id = {cid:<16} | {label}")
    print("\n-> Copy chat_id của NHÓM NHÂN SỰ vào TELEGRAM_ADMIN_CHAT_ID trong .env")


if __name__ == "__main__":
    main()
