"""Lõi "1+2": kết hợp khớp câu hỏi có sẵn với Claude để soạn câu trả lời.

Luồng xử lý:
  1. Tìm các câu Q&A gần giống nhất trong sheet (retriever).
  2. Nếu khớp gần như tuyệt đối (>= EXACT_MATCH_THRESHOLD) -> trả thẳng câu có
     sẵn, không tốn AI, phản hồi tức thì.
  3. Nếu khớp vừa phải -> đưa các câu ứng viên cho Claude để soạn câu trả lời tự
     nhiên, bám sát dữ liệu (chỉ dùng thông tin trong sheet).
  4. Nếu khớp quá thấp / không có AI -> trả câu mặc định (fallback).
"""
from __future__ import annotations

import logging

from anthropic import Anthropic

from .config import settings
from .retriever import Candidate, search

logger = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


SYSTEM_PROMPT = """Bạn là trợ lý chăm sóc khách hàng của một cửa hàng, trả lời bằng tiếng Việt.

Nguyên tắc:
- CHỈ trả lời dựa trên thông tin trong phần "Dữ liệu tham khảo" bên dưới. Tuyệt đối không bịa thêm thông tin (giá, giờ mở cửa, chính sách...) không có trong dữ liệu.
- Nếu dữ liệu không chứa thông tin để trả lời câu hỏi của khách, hãy trả lời đúng một câu: "KHONG_BIET".
- Trả lời ngắn gọn, thân thiện, lịch sự, xưng "shop"/"mình" và gọi khách là "bạn".
- Có thể tổng hợp từ nhiều câu tham khảo nếu cần, nhưng không thêm thông tin ngoài dữ liệu."""


def _compose_with_ai(query: str, candidates: list[Candidate]) -> str:
    context = "\n\n".join(
        f"- Câu hỏi mẫu: {c.pair.question}\n  Trả lời: {c.pair.answer}"
        for c in candidates
    )
    user_content = (
        f"Dữ liệu tham khảo:\n{context}\n\n"
        f"Câu hỏi của khách: {query}\n\n"
        "Hãy soạn câu trả lời cho khách."
    )
    resp = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text


def answer_with_meta(query: str) -> dict:
    """Trả câu trả lời kèm metadata: nguồn (exact/ai/fallback/nearest) và điểm khớp."""
    query = (query or "").strip()
    if not query:
        return {"reply": settings.fallback_answer, "source": "fallback", "score": 0.0}

    candidates = search(query, top_k=settings.top_k)
    if not candidates:
        return {"reply": settings.fallback_answer, "source": "fallback", "score": 0.0}

    top = candidates[0]
    logger.info("Câu hỏi: %r | khớp cao nhất: %.1f (%r)", query, top.score, top.pair.question)

    # Tầng 2: khớp gần như tuyệt đối -> trả thẳng, không tốn AI.
    if top.score >= settings.exact_match_threshold:
        return {"reply": top.pair.answer, "source": "exact", "score": top.score}

    # Khớp quá thấp -> không đủ tin cậy.
    if top.score < settings.min_match_threshold:
        return {"reply": settings.fallback_answer, "source": "fallback", "score": top.score}

    # Tầng 1: dùng AI soạn câu trả lời bám sát dữ liệu.
    if settings.use_ai:
        try:
            ai_text = _compose_with_ai(query, candidates)
            if ai_text and "KHONG_BIET" not in ai_text:
                return {"reply": ai_text, "source": "ai", "score": top.score}
            # Claude báo không đủ dữ liệu.
            return {"reply": settings.fallback_answer, "source": "fallback-ai", "score": top.score}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gọi Claude lỗi (%s), tạm dùng câu khớp gần nhất.", exc)

    # Không có AI (hoặc AI lỗi): dùng câu trả lời khớp gần nhất.
    return {"reply": top.pair.answer, "source": "nearest", "score": top.score}


def answer(query: str) -> str:
    """Trả về câu trả lời cho câu hỏi của khách."""
    return answer_with_meta(query)["reply"]
