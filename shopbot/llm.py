"""Tầng LLM (Claude) — mọi lời gọi model tập trung ở đây.

Định tuyến model theo chi phí:
  - FAST (Haiku): viết lại câu hỏi theo ngữ cảnh + phân loại, trích xuất
    Q&A từ sheet, trích field đơn hàng. Đầu ra JSON theo schema (structured
    outputs) nên không cần parse phòng thủ.
  - SMART (Sonnet): soạn câu trả lời cuối cho khách (bám sát dữ liệu).

Nguyên tắc: prompt hệ thống KHÔNG chứa dữ liệu nghiệp vụ — persona là config,
dữ kiện chỉ đến từ knowledge_entries truyền vào từng lời gọi.
"""
from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from .config import settings

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None

# Chuỗi hiệu lệnh model dùng để báo "dữ liệu không đủ để trả lời"
UNKNOWN_MARKER = "KHONG_BIET"


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


class LLMRefused(RuntimeError):
    """Model từ chối trả lời — caller chuyển sang luồng câu khó."""


def _first_text(response) -> str:
    if response.stop_reason == "refusal":
        raise LLMRefused("model refused")
    return next((b.text for b in response.content if b.type == "text"), "").strip()


async def _json_call(
    model: str, system: str, user: str, schema: dict, max_tokens: int
) -> dict:
    resp = await _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user}],
    )
    return json.loads(_first_text(resp))


# ---------- 1. Viết lại câu hỏi theo ngữ cảnh + định tuyến ----------

_ROUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["question", "order_info", "greeting", "chitchat", "image_request"],
        },
        "standalone_query": {"type": "string"},
    },
    "required": ["kind", "standalone_query"],
    "additionalProperties": False,
}

_ROUTE_SYSTEM = """Bạn phân tích tin nhắn của khách trong hội thoại mua sắm tiếng Việt.

Nhiệm vụ:
1. kind — phân loại tin nhắn mới nhất:
   - "order_info": khách đang CUNG CẤP thông tin đặt hàng (SĐT, địa chỉ, chốt mua...)
   - "greeting": chỉ chào hỏi mở đầu, chưa hỏi gì
   - "chitchat": xã giao/cảm ơn/khen chê không cần dữ liệu shop
   - "image_request": chủ yếu xin xem ảnh (bảng size, mẫu, màu, STK/QR...)
   - "question": còn lại — câu hỏi cần dữ liệu của shop
2. standalone_query — viết lại tin nhắn mới nhất thành MỘT câu hỏi đầy đủ,
   độc lập ngữ cảnh, dựa vào các lượt hội thoại trước. Câu cụt ("giá", "nhiêu",
   "còn không") phải được bổ sung chủ ngữ/đối tượng từ ngữ cảnh.
   Nếu không có ngữ cảnh liên quan thì giữ nguyên ý gốc, KHÔNG bịa thêm.

Chỉ dựa vào hội thoại được cung cấp. Không thêm thông tin ngoài."""


async def route_and_rewrite(history: list[dict], text: str) -> dict:
    """history: [{role: customer|bot|staff, content: str}] các lượt gần nhất."""
    convo = "\n".join(
        f"[{'khách' if m['role'] == 'customer' else 'shop'}]: {m['content']}"
        for m in history
    )
    user = (
        f"Hội thoại gần nhất:\n{convo or '(chưa có)'}\n\n"
        f"Tin nhắn mới nhất của khách: {text}"
    )
    return await _json_call(
        settings.claude_fast_model, _ROUTE_SYSTEM, user, _ROUTE_SCHEMA, 400
    )


# ---------- 2. Soạn câu trả lời cuối (bám sát dữ liệu) ----------

_COMPOSE_SYSTEM_TEMPLATE = """{persona}

Nguyên tắc BẮT BUỘC:
- CHỈ dùng thông tin trong phần "Dữ liệu tham khảo". Tuyệt đối không bịa
  (giá, size, chính sách, số tài khoản, thời gian ship...).
- Nếu dữ liệu không đủ để trả lời đúng câu khách hỏi, trả lời đúng một từ: {marker}
- Trả lời ngắn gọn, tự nhiên, đúng giọng điệu ở trên. Có thể tổng hợp nhiều
  mẫu câu tham khảo, nhưng không thêm dữ kiện ngoài dữ liệu."""


async def compose_answer(
    persona: str, history: list[dict], question: str, entries: list[dict]
) -> str:
    """Trả về câu trả lời, hoặc chuỗi rỗng nếu model báo không đủ dữ liệu."""
    context = "\n\n".join(
        f"- Câu hỏi mẫu: {e['question']}\n  Trả lời mẫu: {e['answer']}"
        for e in entries
    )
    convo = "\n".join(
        f"[{'khách' if m['role'] == 'customer' else 'shop'}]: {m['content']}"
        for m in history
    )
    user = (
        f"Dữ liệu tham khảo:\n{context}\n\n"
        f"Hội thoại gần nhất:\n{convo or '(chưa có)'}\n\n"
        f"Câu hỏi của khách: {question}\n\nSoạn câu trả lời cho khách."
    )
    resp = await _get_client().messages.create(
        model=settings.claude_smart_model,
        max_tokens=700,
        output_config={"effort": "low"},
        system=_COMPOSE_SYSTEM_TEMPLATE.format(persona=persona, marker=UNKNOWN_MARKER),
        messages=[{"role": "user", "content": user}],
    )
    text = _first_text(resp)
    if UNKNOWN_MARKER in text:
        return ""
    return text


async def compose_smalltalk(persona: str, history: list[dict], text: str) -> str:
    """Chào hỏi / xã giao — không được nêu bất kỳ dữ kiện nghiệp vụ nào."""
    convo = "\n".join(
        f"[{'khách' if m['role'] == 'customer' else 'shop'}]: {m['content']}"
        for m in history
    )
    system = (
        f"{persona}\n\nKhách đang chào hỏi/xã giao. Đáp lại ngắn gọn (1-2 câu), "
        "thân thiện, mời khách đặt câu hỏi. TUYỆT ĐỐI không nêu giá, chính sách, "
        "khuyến mãi hay bất kỳ thông tin nghiệp vụ nào."
    )
    resp = await _get_client().messages.create(
        model=settings.claude_fast_model,
        max_tokens=200,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Hội thoại:\n{convo or '(chưa có)'}\n\nKhách nhắn: {text}",
            }
        ],
    )
    return _first_text(resp)


# ---------- 3. Trích xuất Q&A từ sheet (ingest) ----------

_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                    "intent": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["question", "answer", "intent", "category"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["entries"],
    "additionalProperties": False,
}

_EXTRACT_SYSTEM = """Bạn trích xuất cặp Hỏi-Đáp từ một mảng bảng tính "kịch bản tư vấn"
của shop bán hàng online tiếng Việt. Bảng rất lộn xộn: nhiều khối xếp cạnh nhau,
cột không tên chuẩn, lẫn ghi chú.

Với mỗi cặp thực sự là kiến thức tư vấn khách hàng, xuất ra:
- question: câu hỏi/tình huống của khách (viết lại gọn nếu cần)
- answer: câu trả lời mẫu (giữ nguyên nội dung, kể cả emoji)
- intent: nhãn ngắn dạng snake_case tiếng Việt không dấu mô tả ý định
  (vd: hoi_gia, hoi_size, phi_ship, doi_tra, thanh_toan, mau_sac, bang_size...)
- category: tên nhóm dễ đọc (vd: "Giá & thanh toán", "Size & màu", "Vận chuyển")

BỎ QUA (không xuất):
- Dòng tiêu đề khối, đánh số bước kịch bản ("Bước 1", "B2:", ...)
- Phím tắt/lệnh nội bộ (bắt đầu bằng "/", vd /g, /sizeL, /stk)
- Mẫu tin nhắn remind/chăm sóc lại không gắn với câu hỏi của khách
- Ô trống, ghi chú nội bộ cho nhân viên

Cùng một intent có thể có nhiều cặp. Không bịa thêm nội dung không có trong bảng."""


async def extract_entries(chunk_text: str) -> list[dict]:
    data = await _json_call(
        settings.claude_fast_model,
        _EXTRACT_SYSTEM,
        f"Mảng bảng tính:\n{chunk_text}",
        _EXTRACT_SCHEMA,
        4000,
    )
    return data["entries"]


# ---------- 4. Trích field đơn hàng (không bịa) ----------

_ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "phone": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "address": {"type": ["string", "null"]},
        "product": {"type": ["string", "null"]},
        "size": {"type": ["string", "null"]},
        "color": {"type": ["string", "null"]},
        "quantity": {"type": ["string", "null"]},
        "note": {"type": ["string", "null"]},
    },
    "required": [
        "phone", "name", "address", "product", "size", "color", "quantity", "note",
    ],
    "additionalProperties": False,
}

_ORDER_SYSTEM = """Trích thông tin đặt hàng khách CUNG CẤP TRỰC TIẾP trong hội thoại.

Quy tắc tuyệt đối: field nào khách KHÔNG nói rõ thì để null. Không suy đoán,
không lấy từ nguồn nào khác ngoài lời khách. Sản phẩm/size/màu chỉ điền khi
khách đã xác nhận chọn (không điền món khách mới chỉ hỏi thăm)."""


async def extract_order_fields(history: list[dict], text: str) -> dict:
    convo = "\n".join(
        f"[{'khách' if m['role'] == 'customer' else 'shop'}]: {m['content']}"
        for m in history
    )
    user = f"Hội thoại:\n{convo or '(chưa có)'}\n\nTin nhắn mới của khách: {text}"
    return await _json_call(
        settings.claude_fast_model, _ORDER_SYSTEM, user, _ORDER_SCHEMA, 500
    )
