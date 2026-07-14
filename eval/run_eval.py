"""Chạy bộ eval trên pipeline thật (cần DB + API keys + đã ingest).

Dùng: python eval/run_eval.py [eval/questions.yaml]

Đo: đúng intent khớp nhất / câu trả lời chứa chuỗi kỳ vọng / xử lý câu khó
đúng kỳ vọng. In tổng điểm — chạy trước & sau mỗi lần đổi prompt/ngưỡng để
tránh hồi quy.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from shopbot import db, llm  # noqa: E402
from shopbot.config import settings  # noqa: E402
from shopbot.embeddings import embed_text  # noqa: E402


def _parse_history(items: list[str]) -> list[dict]:
    out = []
    for item in items:
        role, _, content = item.partition(":")
        out.append({"role": role.strip(), "content": content.strip()})
    return out


async def run_case(shop_id: int, case: dict) -> tuple[bool, str]:
    history = _parse_history(case.get("history", []))
    text = case["text"]

    route = await llm.route_and_rewrite(history, text)
    query = route["standalone_query"] or text
    vector = await embed_text(query)
    entries = await db.search_knowledge(shop_id, vector, top_k=6)
    top = entries[0] if entries else None
    top_sim = top["similarity"] if top else 0.0
    is_hard = not top or top_sim < settings.min_similarity

    answer = ""
    if not is_hard:
        persona = settings.shop_persona
        answer = await llm.compose_answer(persona, history, query, entries)
        if not answer:
            is_hard = True

    detail = (
        f"query={query!r} sim={top_sim:.2f} "
        f"intent={top['intent'] if top else None} hard={is_hard}"
    )

    if case.get("expect_hard"):
        return is_hard, detail
    if is_hard:
        return False, detail + " (bot bỏ qua trong khi kỳ vọng trả lời)"
    if "expect_intent" in case and top and top["intent"] != case["expect_intent"]:
        return False, detail + f" (kỳ vọng intent {case['expect_intent']})"
    if "expect_contains" in case and case["expect_contains"] not in answer:
        return False, detail + f" (thiếu chuỗi {case['expect_contains']!r})"
    return True, detail


async def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "eval/questions.yaml"
    data = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    cases = data["cases"]

    shop_id = await db.ensure_shop(settings.shop_slug, settings.shop_name)
    passed = 0
    for i, case in enumerate(cases, 1):
        ok, detail = await run_case(shop_id, case)
        passed += ok
        print(f"{'✅' if ok else '❌'} case {i}: {case['text']!r}\n   {detail}")
    print(f"\nKết quả: {passed}/{len(cases)} đạt")
    await db.close_pool()
    if passed < len(cases):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
