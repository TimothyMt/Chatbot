"""Đơn hàng: trích field có cấu trúc + xác nhận bằng TEMPLATE CỐ ĐỊNH.

Chống bịa: LLM chỉ trích field khách nói (field thiếu = null); câu xác nhận
do CODE điền template, model không được tự soạn văn xác nhận đơn.
"""
from __future__ import annotations

_FIELD_LABELS = [
    ("name", "Tên"),
    ("phone", "SĐT"),
    ("address", "Địa chỉ"),
    ("product", "Sản phẩm"),
    ("size", "Size"),
    ("color", "Màu"),
    ("quantity", "Số lượng"),
    ("note", "Ghi chú"),
]

# Field tối thiểu để đơn coi là gửi được cho nhân sự xử lý
_REQUIRED = ["phone", "address"]

_ASK_LABELS = {"phone": "số điện thoại", "address": "địa chỉ nhận hàng"}


def provided_fields(fields: dict) -> dict:
    """Chỉ giữ field có giá trị thật (khác None/rỗng)."""
    return {
        k: str(v).strip()
        for k, v in fields.items()
        if v is not None and str(v).strip()
    }


def missing_required(fields: dict) -> list[str]:
    got = provided_fields(fields)
    return [k for k in _REQUIRED if k not in got]


def render_confirmation(fields: dict) -> str:
    """Câu xác nhận: chỉ liệt kê đúng những gì khách cung cấp, hỏi phần thiếu."""
    got = provided_fields(fields)
    lines = ["Dạ em xin xác nhận thông tin mình gửi ạ:"]
    for key, label in _FIELD_LABELS:
        if key in got:
            lines.append(f"• {label}: {got[key]}")
    missing = missing_required(fields)
    if missing:
        need = " và ".join(_ASK_LABELS[k] for k in missing)
        lines.append(f"Chị cho em xin thêm {need} để lên đơn giúp mình nhé ạ 💕")
    else:
        lines.append("Em gửi thông tin cho bộ phận lên đơn ngay ạ, "
                     "mình chờ shop xác nhận chút xíu nha 💕")
    return "\n".join(lines)


def render_staff_alert(fields: dict, raw_text: str, customer_ref: str) -> str:
    got = provided_fields(fields)
    lines = ["🛒 CHỐT ĐƠN MỚI", f"Khách: {customer_ref}"]
    for key, label in _FIELD_LABELS:
        if key in got:
            lines.append(f"• {label}: {got[key]}")
    missing = missing_required(fields)
    if missing:
        lines.append("⚠️ Còn thiếu: " + ", ".join(_ASK_LABELS[k] for k in missing))
    lines.append(f"— Tin gốc: {raw_text}")
    return "\n".join(lines)
