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
        text = ""
        source = ""
        url = settings.sheet_csv_url
        if url:
            try:
                resp = httpx.get(url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                text = resp.text
                source = f"Google Sheet ({url})"
            except Exception as exc:  # noqa: BLE001
                logger.warning("Không tải được Google Sheet (%s), dùng CSV local.", exc)

        if not text:
            path = Path(settings.qa_csv_path)
            if path.exists():
                text = path.read_text(encoding="utf-8")
                source = f"file local ({path})"

        pairs = _parse_pairs(text) if text else []
        self._pairs = pairs
        self._loaded_at = time.time()
        logger.info("Đã nạp %d câu Q&A từ %s", len(pairs), source or "không có nguồn")
        return len(pairs)


def _parse_pairs(text: str) -> list[QAPair]:
    """Chuyển nội dung CSV thành danh sách QAPair theo cấu hình.

    - Nếu QA_COLUMN_PAIRS được đặt: đọc theo vị trí cột (hỗ trợ sheet nhiều khối).
    - Ngược lại: đọc theo tên cột question/answer.
    """
    pairs: list[QAPair] = []
    if settings.qa_column_pairs:
        col_pairs = _parse_column_pairs(settings.qa_column_pairs)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)[settings.qa_skip_rows:]
        for row in rows:
            for qi, ai in col_pairs:
                q = row[qi].strip() if qi < len(row) else ""
                a = row[ai].strip() if ai < len(row) else ""
                if q and a:
                    pairs.append(QAPair(question=q, answer=a))
    else:
        qcol, acol = settings.qa_question_column, settings.qa_answer_column
        for row in csv.DictReader(io.StringIO(text)):
            q = (row.get(qcol) or "").strip()
            a = (row.get(acol) or "").strip()
            if q and a:
                pairs.append(QAPair(question=q, answer=a))
    return pairs


def _parse_column_pairs(spec: str) -> list[tuple[int, int]]:
    """'2:3,7:8,11:12' -> [(2,3),(7,8),(11,12)]"""
    out: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        q, a = part.split(":")
        out.append((int(q), int(a)))
    return out


knowledge_base = KnowledgeBase()
