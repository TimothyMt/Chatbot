"""Tầng khớp câu hỏi: tìm các câu Q&A gần giống nhất bằng thuật toán fuzzy."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .knowledge import QAPair, knowledge_base


def _normalize(text: str) -> str:
    """Chuẩn hoá: bỏ dấu, viết thường, gọn khoảng trắng để so khớp tốt hơn."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.split())


@dataclass
class Candidate:
    pair: QAPair
    score: float


def search(query: str, top_k: int = 5) -> list[Candidate]:
    """Trả về top_k câu Q&A gần giống nhất, sắp theo điểm giảm dần.

    Điểm khớp = max(khớp với câu hỏi, 0.9 * khớp với nội dung trả lời).
    Khớp thêm với nội dung trả lời giúp tìm ra câu đúng khi cách khách hỏi
    khác hẳn cách ghi câu hỏi trong sheet, nhưng câu trả lời lại chứa từ khoá.
    """
    pairs = knowledge_base.pairs
    if not pairs:
        return []

    norm_query = _normalize(query)
    scored: list[Candidate] = []
    for p in pairs:
        score_q = fuzz.token_set_ratio(norm_query, _normalize(p.question))
        # Chỉ lấy phần đầu câu trả lời để giảm nhiễu do câu trả lời quá dài.
        score_a = fuzz.token_set_ratio(norm_query, _normalize(p.answer[:250]))
        score = max(score_q, 0.9 * score_a)
        scored.append(Candidate(pair=p, score=score))

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]
