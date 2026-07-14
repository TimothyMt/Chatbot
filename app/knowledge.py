"""Nạp danh sách câu hỏi - câu trả lời từ Google Sheets hoặc file CSV."""
from __future__ import annotations

import csv
import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class QAPair:
    question: str
    answer: str


class KnowledgeBase:
    """Giữ danh sách Q&A trong bộ nhớ, có cache và tự làm mới theo TTL."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._pairs: list[QAPair] = []
        self._loaded_at: float = 0.0
        self._ttl = ttl_seconds

    @property
    def pairs(self) -> list[QAPair]:
        if not self._pairs or (time.time() - self._loaded_at) > self._ttl:
            self.reload()
        return self._pairs

    def reload(self) -> int:
        """Tải lại dữ liệu. Ưu tiên Google Sheet, fallback về CSV local."""
        rows: list[dict[str, str]] = []
        source = ""
        url = settings.sheet_csv_url
        if url:
            try:
                resp = httpx.get(url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                rows = list(csv.DictReader(io.StringIO(resp.text)))
                source = f"Google Sheet ({url})"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Không tải được Google Sheet (%s), dùng CSV local.", exc)

        if not rows:
            path = Path(settings.qa_csv_path)
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                source = f"file local ({path})"

        pairs: list[QAPair] = []
        qcol, acol = settings.qa_question_column, settings.qa_answer_column
        for row in rows:
            q = (row.get(qcol) or "").strip()
            a = (row.get(acol) or "").strip()
            if q and a:
                pairs.append(QAPair(question=q, answer=a))

        self._pairs = pairs
        self._loaded_at = time.time()
        logger.info("Đã nạp %d câu Q&A từ %s", len(pairs), source or "không có nguồn")
        return len(pairs)


knowledge_base = KnowledgeBase()
