"""Tiện ích chuẩn hoá văn bản tiếng Việt (dùng cho cache key, dedup)."""
from __future__ import annotations

import unicodedata


def normalize(text: str) -> str:
    """Viết thường, bỏ dấu, gọn khoảng trắng. CHỈ dùng làm khoá so sánh,
    không dùng để hiểu ngữ nghĩa (việc đó thuộc về embeddings/LLM)."""
    text = (text or "").lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.split())
