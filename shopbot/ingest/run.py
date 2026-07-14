"""Điều phối ingest: sheet -> chunks -> LLM trích xuất -> dedup -> embed -> DB.

Versioning: mỗi lần chạy là một ingest_run; entry cũ chỉ bị 'superseded' khi
run mới ghi thành công (transaction). Run lỗi -> dữ liệu cũ giữ nguyên.
"""
from __future__ import annotations

import asyncio
import logging

from .. import db
from ..config import settings
from ..embeddings import embed_texts
from ..llm import extract_entries
from ..textutil import normalize
from .blocks import grid_to_chunks
from .sheet import fetch_grid

logger = logging.getLogger(__name__)

_EXTRACT_CONCURRENCY = 4


def dedup_entries(entries: list[dict]) -> list[dict]:
    """Loại trùng theo câu hỏi chuẩn hoá; loại entry thiếu ruột."""
    seen: set[str] = set()
    out: list[dict] = []
    for e in entries:
        q = (e.get("question") or "").strip()
        a = (e.get("answer") or "").strip()
        if len(q) < 2 or len(a) < 2:
            continue
        key = normalize(q)
        if key in seen:
            continue
        seen.add(key)
        out.append({**e, "question": q, "answer": a})
    return out


async def _extract_all(chunks: list[str]) -> list[dict]:
    sem = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

    async def one(chunk: str) -> list[dict]:
        async with sem:
            try:
                return await extract_entries(chunk)
            except Exception:
                logger.exception("Trích xuất 1 chunk lỗi, bỏ qua chunk này")
                return []

    results = await asyncio.gather(*(one(c) for c in chunks))
    return [e for group in results for e in group]


async def run_ingest(shop_id: int, sheet_urls: str | None = None) -> dict:
    """Chạy một lượt ingest đầy đủ. Trả về stats. Raise nếu lỗi tổng thể."""
    urls = [u for u in (sheet_urls or settings.sheet_urls).split(",") if u.strip()]
    if not urls:
        raise ValueError("Chưa cấu hình SHEET_URLS")

    run_id = await db.create_ingest_run(shop_id, ",".join(urls))
    try:
        chunks: list[str] = []
        for url in urls:
            grid = await fetch_grid(url)
            chunks.extend(grid_to_chunks(grid))
        logger.info("Ingest run %s: %d chunk từ %d sheet", run_id, len(chunks), len(urls))

        raw = await _extract_all(chunks)
        entries = dedup_entries(raw)
        if not entries:
            raise ValueError("Không trích xuất được Q&A nào từ sheet")

        # Embed "câu hỏi + đầu câu trả lời" để tăng recall khi khách hỏi khác cách
        vectors = await embed_texts(
            [f"{e['question']}\n{e['answer'][:200]}" for e in entries]
        )
        for e, v in zip(entries, vectors):
            e["embedding"] = v

        count = await db.activate_ingest_entries(shop_id, run_id, entries)
        stats = {
            "sheets": len(urls),
            "chunks": len(chunks),
            "raw_entries": len(raw),
            "entries": count,
        }
        await db.finish_ingest_run(run_id, "succeeded", stats)
        logger.info("Ingest run %s xong: %s", run_id, stats)
        return stats
    except Exception as exc:
        await db.finish_ingest_run(run_id, "failed", error=str(exc))
        raise
