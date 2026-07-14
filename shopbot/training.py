"""Vòng học: nhân viên dạy -> hàng đợi duyệt -> kích hoạt vào kho tri thức.

Luồng chính (trong nhóm hỗ trợ):
  1. Bot báo "câu khó" kèm ID tin nhắn alert.
  2. Nhân viên REPLY vào alert bằng câu trả lời đúng
     -> gửi ngay cho khách + tạo pending_teaching + nút ✅/❌.
  3. Ai đó bấm ✅ -> embed + ghi knowledge_entries (source='taught')
     -> lần sau bot tự trả lời. Bấm ❌ -> bỏ.
Ngoài ra có lệnh /day <câu hỏi> | <câu trả lời> để dạy trực tiếp.
"""
from __future__ import annotations

import logging

from . import db
from .answer import answer_cache
from .embeddings import embed_text

logger = logging.getLogger(__name__)


def parse_teach_command(text: str) -> tuple[str, str] | None:
    """'/day câu hỏi | câu trả lời' -> (q, a) hoặc None nếu sai cú pháp."""
    body = text.split(maxsplit=1)
    if len(body) < 2:
        return None
    parts = body[1].split("|", 1)
    if len(parts) != 2:
        return None
    q, a = parts[0].strip(), parts[1].strip()
    if not q or not a:
        return None
    return q, a


def parse_callback(data: str) -> tuple[str, int] | None:
    """'teach:ok:123' -> ('ok', 123)."""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "teach":
        return None
    action = parts[1]
    if action not in ("ok", "no"):
        return None
    try:
        return action, int(parts[2])
    except ValueError:
        return None


def render_pending_notice(teaching_id: int, question: str, answer: str) -> str:
    return (
        f"📚 CÂU HỌC MỚI #{teaching_id} (chờ duyệt)\n"
        f"Hỏi: {question}\n"
        f"Đáp: {answer}\n"
        f"Duyệt thì bot sẽ tự trả lời câu này từ lần sau."
    )


async def submit_teaching(
    shop_id: int,
    question: str,
    answer: str,
    taught_by: str,
    conversation_id: int | None = None,
) -> int:
    return await db.create_pending_teaching(
        shop_id, question, answer, taught_by, conversation_id
    )


async def approve_teaching(teaching_id: int, reviewed_by: str) -> str:
    """Trả về chuỗi mô tả kết quả để hiển thị lại trong nhóm."""
    teaching = await db.get_pending_teaching(teaching_id)
    if not teaching:
        return f"Không tìm thấy câu học #{teaching_id}."
    if teaching["status"] != "pending":
        return f"Câu học #{teaching_id} đã được xử lý ({teaching['status']})."

    vector = await embed_text(
        f"{teaching['question']}\n{teaching['answer'][:200]}"
    )
    entry_id = await db.insert_taught_entry(
        teaching["shop_id"],
        teaching["question"],
        teaching["answer"],
        vector,
        teaching["taught_by"] or "",
        reviewed_by,
    )
    await db.resolve_pending_teaching(teaching_id, "approved", reviewed_by, entry_id)
    answer_cache.clear()  # tri thức đổi -> bỏ cache cũ
    return (
        f"✅ Đã duyệt câu học #{teaching_id} (entry {entry_id}). "
        f"Bot sẽ tự trả lời câu này từ giờ."
    )


async def reject_teaching(teaching_id: int, reviewed_by: str) -> str:
    teaching = await db.get_pending_teaching(teaching_id)
    if not teaching:
        return f"Không tìm thấy câu học #{teaching_id}."
    if teaching["status"] != "pending":
        return f"Câu học #{teaching_id} đã được xử lý ({teaching['status']})."
    await db.resolve_pending_teaching(teaching_id, "rejected", reviewed_by, None)
    return f"❌ Đã bỏ câu học #{teaching_id}."
