"""Script test hiển thị rõ mỗi câu được trả lời bằng tầng nào.

Chạy:  python test_ai.py
Cần:   ANTHROPIC_API_KEY trong .env để thấy tầng AI hoạt động (không có key vẫn
       chạy được nhưng chỉ có tầng khớp).

Nhãn nguồn:
  exact       -> khớp gần tuyệt đối, trả thẳng câu có sẵn (không tốn AI)
  ai          -> Claude soạn câu trả lời dựa trên các câu ứng viên trong sheet
  fallback    -> không tìm được thông tin phù hợp, trả câu mặc định
  fallback-ai -> Claude xác định sheet không có thông tin -> câu mặc định
  nearest     -> không bật AI, dùng tạm câu khớp gần nhất
"""
from __future__ import annotations

from app.config import settings
from app.knowledge import knowledge_base
from app.responder import answer_with_meta

# Sửa/thêm câu hỏi test ở đây cho phù hợp dữ liệu của bạn.
QUESTIONS = [
    "shop mở cửa lúc mấy giờ vậy?",
    "ship về Cà Mau mất bao lâu và bao nhiêu tiền?",
    "mua rồi không ưng có trả lại được không",
    "có ship hàng ra nước ngoài không?",
    "shop bán iphone không",
]


def main() -> None:
    count = knowledge_base.reload()
    print(f"Đã nạp {count} câu Q&A | AI={'BẬT' if settings.use_ai else 'TẮT'}\n")
    for q in QUESTIONS:
        meta = answer_with_meta(q)
        print(f"Khách : {q}")
        print(f"Nguồn : {meta['source']} (điểm khớp {meta['score']:.0f})")
        print(f"Bot   : {meta['reply']}\n")


if __name__ == "__main__":
    main()
