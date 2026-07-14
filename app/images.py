"""Chọn ảnh để gửi cho khách dựa trên từ khoá trong câu hỏi.

Dữ liệu ảnh nằm ở data/images.csv với các cột:
  keywords    : các từ khoá cách nhau bởi dấu '|' (không dấu cũng được)
  image_url   : link ảnh công khai (Telegram/Facebook sẽ tự tải link này)
  caption     : chú thích gửi kèm ảnh (có thể để trống)
"""
from __future__ import annotations

import csv
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import settings


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.split())


@dataclass
class ImageRule:
    keywords: list[str]
    url: str
    caption: str


class ImageLibrary:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._rules: list[ImageRule] = []
        self._loaded_at = 0.0
        self._ttl = ttl_seconds

    @property
    def rules(self) -> list[ImageRule]:
        if not self._rules or (time.time() - self._loaded_at) > self._ttl:
            self.reload()
        return self._rules

    def reload(self) -> int:
        rules: list[ImageRule] = []
        path = Path(settings.images_csv_path)
        if path.exists():
            with path.open(encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    url = (row.get("image_url") or "").strip()
                    if not url:
                        continue
                    kws = [
                        _normalize(k)
                        for k in (row.get("keywords") or "").split("|")
                        if k.strip()
                    ]
                    rules.append(
                        ImageRule(keywords=kws, url=url, caption=(row.get("caption") or "").strip())
                    )
        self._rules = rules
        self._loaded_at = time.time()
        return len(rules)

    def match(self, query: str) -> list[ImageRule]:
        """Trả về các ảnh có từ khoá xuất hiện trong câu hỏi của khách."""
        norm = _normalize(query)
        return [r for r in self.rules if any(kw in norm for kw in r.keywords)]


image_library = ImageLibrary()
