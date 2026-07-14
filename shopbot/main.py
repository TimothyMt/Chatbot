"""FastAPI app: webhook Telegram (trả 200 ngay, xử lý nền) + endpoint vận hành."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from . import db
from .config import settings
from .ingest.run import run_ingest
from .telegram.router import Router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

router: Router | None = None
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    """Chạy nền, giữ tham chiếu để task không bị GC nuốt."""
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global router
    shop_id = await db.ensure_shop(settings.shop_slug, settings.shop_name)
    router = Router(shop_id)
    logger.info("Khởi động: shop_id=%s slug=%s", shop_id, settings.shop_slug)
    yield
    await db.close_pool()


app = FastAPI(title="Shop CSKH Bot", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    pool = await db.get_pool()
    knowledge = await pool.fetchval(
        "select count(*) from knowledge_entries where status='active'"
    )
    return {"status": "ok", "active_knowledge": knowledge}


@app.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> PlainTextResponse:
    if settings.telegram_webhook_secret and (
        x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403, detail="bad secret")
    update = await request.json()
    assert router is not None
    # Trả 200 ngay để Telegram không retry; xử lý (kể cả dedup) chạy nền
    _spawn(router.handle_update(update))
    return PlainTextResponse("OK")


@app.post("/ingest")
async def ingest_endpoint(
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Chạy lại ingest thủ công (bảo vệ bằng chính token Telegram làm admin token)."""
    if not settings.telegram_bot_token or x_admin_token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="bad token")
    assert router is not None
    stats = await run_ingest(router.shop_id)
    from .answer import answer_cache

    answer_cache.clear()
    return {"ok": True, **stats}
