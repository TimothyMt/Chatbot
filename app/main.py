"""FastAPI app: endpoint /chat để test + webhook Messenger và Zalo."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .channels import messenger, telegram, zalo
from .config import settings
from .images import image_library
from .knowledge import knowledge_base
from .pipeline import process_message
from .responder import answer

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Customer Chatbot")


@app.on_event("startup")
def _startup() -> None:
    count = knowledge_base.reload()
    img = image_library.reload()
    logging.info("Khởi động: %d câu Q&A, %d nhóm ảnh, AI=%s", count, img, settings.use_ai)


# ---------- API test ----------
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "qa_count": len(knowledge_base.pairs), "ai": settings.use_ai}


@app.post("/reload")
def reload_kb() -> dict:
    """Nạp lại dữ liệu Q&A và thư viện ảnh ngay lập tức."""
    return {"qa_count": knowledge_base.reload(), "image_rules": image_library.reload()}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    return ChatResponse(reply=answer(req.message))


# ---------- Facebook Messenger ----------
@app.get("/webhook/messenger")
def messenger_verify(
    mode: str | None = Query(None, alias="hub.mode"),
    token: str | None = Query(None, alias="hub.verify_token"),
    challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    result = messenger.verify(mode, token, challenge)
    if result is None:
        return PlainTextResponse("Verification failed", status_code=403)
    return PlainTextResponse(result)


@app.post("/webhook/messenger")
async def messenger_webhook(request: Request) -> Response:
    body = await request.json()
    for sender_id, text in messenger.extract_messages(body):
        reply = await process_message("messenger", sender_id, text)
        if reply.text.strip():
            await messenger.send_message(sender_id, reply.text)
        for url, caption in reply.images:
            await messenger.send_image(sender_id, url, caption)
    return PlainTextResponse("EVENT_RECEIVED")


# ---------- Zalo OA ----------
@app.post("/webhook/zalo")
async def zalo_webhook(request: Request) -> Response:
    body = await request.json()
    for user_id, text in zalo.extract_messages(body):
        reply = await process_message("zalo", user_id, text)
        if reply.text.strip():
            await zalo.send_message(user_id, reply.text)
        for url, caption in reply.images:
            await zalo.send_image(user_id, url, caption)
    return PlainTextResponse("OK")


# ---------- Telegram (webhook — dùng khi deploy; test thì chạy run_telegram.py) ----------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> Response:
    update = await request.json()
    for m in telegram.extract_messages(update):
        if m.chat_type == "private":
            # Khách chat riêng với bot.
            reply = await process_message("telegram", m.chat_id, m.text)
            if reply.text.strip():
                await telegram.send_message(m.chat_id, reply.text)
            for url, caption in reply.images:
                await telegram.send_photo(m.chat_id, url, caption)
            continue

        # Trong nhóm nhân sự: nếu nhân viên REPLY vào thông báo -> chuyển lời tới khách.
        if m.chat_id == settings.telegram_admin_chat_id and m.reply_to_text:
            customer_id = telegram.parse_customer_from_alert(m.reply_to_text)
            if customer_id:
                await telegram.send_message(customer_id, m.text)
                await telegram.send_message(m.chat_id, f"✅ Đã gửi tới khách {customer_id}.")
                continue
        logging.info("Tin trong %s chat_id=%s (không trả lời)", m.chat_type, m.chat_id)
    return PlainTextResponse("OK")
