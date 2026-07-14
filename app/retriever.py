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
    """Trả về top_k câu Q&A gần giống nhất, sắp theo điểm giảm dần."""
    pairs = knowledge_base.pairs
    if not pairs:
        return []

    norm_query = _normalize(query)
    # Ánh xạ câu hỏi đã chuẩn hoá -> pair gốc
    choices = {i: _normalize(p.question) for i, p in enumerate(pairs)}

    results = process.extract(
        norm_query,
        choices,
        scorer=fuzz.token_set_ratio,
        limit=top_k,
    )
    # process.extract trả về (matched_text, score, key)
    return [Candidate(pair=pairs[key], score=score) for _, score, key in results]
