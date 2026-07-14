"""Chat thử trong terminal, không cần webhook.

Chạy: python cli.py
Gõ câu hỏi, gõ 'quit' để thoát.
"""
from __future__ import annotations

from app.knowledge import knowledge_base
from app.responder import answer


def main() -> None:
    count = knowledge_base.reload()
    print(f"Đã nạp {count} câu Q&A. Gõ câu hỏi (hoặc 'quit' để thoát).\n")
    while True:
        try:
            query = input("Khách: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if query.lower() in {"quit", "exit", "thoat"}:
            break
        if not query:
            continue
        print(f"Bot : {answer(query)}\n")


if __name__ == "__main__":
    main()
