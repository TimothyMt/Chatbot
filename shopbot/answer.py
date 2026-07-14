"""Luồng trả lời khách: gộp tin -> viết lại theo ngữ cảnh -> semantic search
-> quyết định -> soạn trả lời / chốt đơn / báo câu khó.

An toàn: similarity thấp hoặc model báo thiếu dữ liệu -> KHÔNG trả lời khách,
chỉ báo nhóm nhân sự (kèm câu giữ chân nếu shop bật HOLDING_MESSAGE).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from . import db, llm, orders
from .config import settings
from .embeddings import embed_text
from .textutil import normalize

logger = logging.getLogger(__name__)


@dataclass
class Reply:
    texts: list[str] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)  # {file_id|url, caption}
    # Thông báo nội bộ: (target_group, text) — router gửi đi và gắn alert id
    order_alert: str | None = None
    hard_question_id: int | None = None
    hard_alert_text: str | None = None


class _AnswerCache:
    """Cache in-memory cho câu hỏi lặp lại y hệt (đã chuẩn hoá)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str, list[dict]]] = {}

    def get(self, key: str) -> tuple[str, list[dict]] | None:
        if settings.answer_cache_ttl <= 0:
            return None
        item = self._store.get(key)
        if not item:
            return None
        ts, text, images = item
        if time.time() - ts > settings.answer_cache_ttl:
            self._store.pop(key, None)
            return None
        return text, images

    def put(self, key: str, text: str, images: list[dict]) -> None:
        if settings.answer_cache_ttl > 0:
            self._store[key] = (time.time(), text, images)

    def clear(self) -> None:
        self._store.clear()


answer_cache = _AnswerCache()


async def _persona(shop_id: int) -> str:
    return await db.get_config(shop_id, "persona", settings.shop_persona)


async def _go_hard_question(
    shop_id: int, conversation_id: int, question: str, reply: Reply, reason: str
) -> Reply:
    """Câu khó: im lặng với khách (hoặc câu giữ chân), báo nhóm hỗ trợ."""
    hard_id = await db.create_hard_question(shop_id, conversation_id, question)
    reply.hard_question_id = hard_id
    reply.hard_alert_text = (
        f"❓ CÂU KHÓ #{hard_id} ({reason})\n"
        f"Khách hỏi: {question}\n"
        f"👉 Reply tin này để trả lời khách — câu trả lời sẽ vào hàng đợi duyệt "
        f"để dạy bot."
    )
    holding = await db.get_config(shop_id, "holding_message", settings.holding_message)
    if holding:
        reply.texts.append(holding)
    return reply


async def handle_customer_message(
    shop_id: int, conversation_id: int, text: str
) -> Reply:
    """Xử lý một lượt (đã gộp debounce) của khách. Trả về Reply cho router gửi."""
    started = time.monotonic()
    reply = Reply()
    history = await db.recent_messages(conversation_id, settings.history_limit)
    await db.log_message(conversation_id, "customer", text)

    # 1. Viết lại theo ngữ cảnh + định tuyến (model rẻ)
    try:
        route = await llm.route_and_rewrite(history, text)
    except Exception:
        logger.exception("route_and_rewrite lỗi")
        return await _go_hard_question(
            shop_id, conversation_id, text, reply, "lỗi phân tích"
        )
    kind = route["kind"]
    query = route["standalone_query"].strip() or text

    # 2. Khách cung cấp thông tin đặt hàng -> trích field + template cố định
    if kind == "order_info":
        return await _handle_order(shop_id, conversation_id, history, text, reply)

    # 3. Chào hỏi / xã giao — không đụng dữ liệu nghiệp vụ
    if kind in ("greeting", "chitchat"):
        try:
            small = await llm.compose_smalltalk(await _persona(shop_id), history, text)
        except Exception:
            logger.exception("compose_smalltalk lỗi")
            small = ""
        if small:
            reply.texts.append(small)
            await db.log_message(
                conversation_id, "bot", small, {"source": "smalltalk", "kind": kind}
            )
        return reply

    # 4. Câu hỏi cần dữ liệu (kể cả image_request): semantic search
    cache_key = normalize(query)
    cached = answer_cache.get(cache_key)
    if cached:
        cached_text, cached_images = cached
        reply.texts.append(cached_text)
        reply.images.extend(cached_images)
        await db.log_message(
            conversation_id, "bot", cached_text,
            {"source": "cache", "rewritten_query": query},
        )
        return reply

    try:
        vector = await embed_text(query)
        entries = await db.search_knowledge(shop_id, vector, top_k=6)
    except Exception:
        logger.exception("semantic search lỗi")
        return await _go_hard_question(
            shop_id, conversation_id, query, reply, "lỗi tìm kiếm"
        )

    top_sim = entries[0]["similarity"] if entries else 0.0
    if not entries or top_sim < settings.min_similarity:
        return await _go_hard_question(
            shop_id, conversation_id, query, reply,
            f"không có dữ liệu khớp (sim={top_sim:.2f})",
        )

    # 5. Soạn trả lời bám sát dữ liệu (model lớn); KHONG_BIET -> câu khó
    try:
        answer_text = await llm.compose_answer(
            await _persona(shop_id), history, query, entries
        )
    except llm.LLMRefused:
        answer_text = ""
    except Exception:
        logger.exception("compose_answer lỗi")
        return await _go_hard_question(
            shop_id, conversation_id, query, reply, "lỗi soạn trả lời"
        )
    if not answer_text:
        return await _go_hard_question(
            shop_id, conversation_id, query, reply, "dữ liệu chưa đủ để trả lời"
        )

    # 6. Ảnh theo intent của entry khớp nhất (nếu shop đã đăng ký ảnh)
    images: list[dict] = []
    top_intent = entries[0].get("intent")
    if top_intent and top_sim >= settings.min_similarity:
        images = await db.images_for_intent(shop_id, top_intent)

    reply.texts.append(answer_text)
    reply.images.extend(images)
    if top_sim >= settings.high_similarity:
        answer_cache.put(cache_key, answer_text, images)

    await db.log_message(
        conversation_id, "bot", answer_text,
        {
            "source": "ai",
            "similarity": round(top_sim, 3),
            "intent": top_intent,
            "used_entry_ids": [e["id"] for e in entries[:3]],
            "rewritten_query": query,
            "latency_ms": int((time.monotonic() - started) * 1000),
        },
    )
    return reply


async def _handle_order(
    shop_id: int,
    conversation_id: int,
    history: list[dict],
    text: str,
    reply: Reply,
) -> Reply:
    try:
        fields = await llm.extract_order_fields(history, text)
    except Exception:
        logger.exception("extract_order_fields lỗi")
        return await _go_hard_question(
            shop_id, conversation_id, text, reply, "lỗi trích đơn"
        )

    got = orders.provided_fields(fields)
    confirmation = orders.render_confirmation(fields)
    reply.texts.append(confirmation)
    await db.log_message(
        conversation_id, "bot", confirmation, {"source": "order_template"}
    )

    # Chỉ tạo đơn + báo nhóm chốt đơn khi có ít nhất 1 field thực
    if got:
        await db.create_order(shop_id, conversation_id, got, text)
        target = await db.get_conversation_target(conversation_id)
        customer_ref = (
            f"{target['channel']} {target['external_user_id']}" if target else "?"
        )
        reply.order_alert = orders.render_staff_alert(fields, text, customer_ref)
    return reply
