"""Đăng ký webhook Telegram (chạy 1 lần sau khi deploy).

Dùng: python scripts/set_webhook.py https://<app>.up.railway.app
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from shopbot.config import settings  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("Dùng: python scripts/set_webhook.py https://<domain>")
        sys.exit(1)
    base = sys.argv[1].rstrip("/")
    payload = {
        "url": f"{base}/webhook/telegram",
        "allowed_updates": ["message", "callback_query"],
        "drop_pending_updates": True,
    }
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret
    resp = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
        json=payload,
        timeout=20,
    )
    print(resp.status_code, resp.text)


if __name__ == "__main__":
    main()
