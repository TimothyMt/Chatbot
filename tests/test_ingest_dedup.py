from shopbot.ingest.run import dedup_entries
from shopbot.textutil import normalize


def test_normalize():
    assert normalize("  Bảng   SIZE  ") == "bang size"
    assert normalize("Màu") == normalize("màu")


def test_dedup_by_normalized_question():
    entries = [
        {"question": "Phí ship bao nhiêu?", "answer": "30k", "intent": "phi_ship", "category": "Ship"},
        {"question": "phi ship bao nhieu?", "answer": "30k ạ", "intent": "phi_ship", "category": "Ship"},
        {"question": "Đổi trả thế nào", "answer": "7 ngày", "intent": "doi_tra", "category": "Đổi trả"},
    ]
    out = dedup_entries(entries)
    assert len(out) == 2
    assert out[0]["question"] == "Phí ship bao nhiêu?"


def test_dedup_drops_empty():
    entries = [
        {"question": "", "answer": "x", "intent": "a", "category": "b"},
        {"question": "q", "answer": " ", "intent": "a", "category": "b"},
        {"question": "hợp lệ", "answer": "đáp", "intent": "a", "category": "b"},
    ]
    out = dedup_entries(entries)
    assert len(out) == 1
    assert out[0]["question"] == "hợp lệ"
