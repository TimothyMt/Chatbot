"""FastAPI app: endpoint /chat để test + webhook Messenger và Zalo."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .channels import messenger, zalo
from .config import settings
from .knowledge import knowledge_base
from .responder import answer

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Customer Chatbot")


@app.on_event("startup")
def _startup() -> None:
    count = knowledge_base.reload()
    logging.info("Khởi động: %d câu Q&A, AI=%s", count, settings.use_ai)


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
    """Nạp lại dữ liệu Q&A từ Google Sheet ngay lập tức."""
    return {"qa_count": knowledge_base.reload()}


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
        reply = answer(text)
        await messenger.send_message(sender_id, reply)
    return PlainTextResponse("EVENT_RECEIVED")


# ---------- Zalo OA ----------
@app.post("/webhook/zalo")
async def zalo_webhook(request: Request) -> Response:
    body = await request.json()
    for user_id, text in zalo.extract_messages(body):
        reply = answer(text)
        await zalo.send_message(user_id, reply)
    return PlainTextResponse("OK")
