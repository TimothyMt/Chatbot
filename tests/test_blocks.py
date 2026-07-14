"""Test cắt khối sheet Pancake nhiều khối xếp cạnh nhau."""
from shopbot.ingest.blocks import chunk_rows, grid_to_chunks, split_column_groups

# Mô phỏng sheet thật: 2 khối cạnh nhau ngăn bởi cột trống, lẫn nhiễu
GRID = [
    ["KỊCH BẢN TƯ VẤN", "", "", "", "CÁC MẪU CÂU KHÁC", ""],
    ["Bước 1: Chào khách", "", "", "", "Khách hỏi phí ship", "Dạ phí ship 30k ạ"],
    ["Khách hỏi giá", "Dạ váy bên em 350k ạ", "", "", "/stk", "0123456789 - NH ABC"],
    ["Khách hỏi size", "Dạ mình cao bao nhiêu ạ?", "", "", "", ""],
    ["", "", "", "", "Khách hỏi đổi trả", "Dạ được đổi trong 7 ngày ạ"],
]


def test_split_column_groups_two_blocks():
    groups = split_column_groups(GRID)
    assert len(groups) == 2
    left, right = groups
    assert any("Khách hỏi giá" in " ".join(r) for r in left)
    assert any("phí ship" in " ".join(r) for r in right)
    # Khối trái không lẫn nội dung khối phải
    assert not any("đổi trả" in " ".join(r) for r in left)


def test_empty_grid():
    assert split_column_groups([]) == []
    assert grid_to_chunks([]) == []


def test_chunk_rows_includes_header_context():
    sub = [["TIÊU ĐỀ KHỐI"], ["header 2"]] + [[f"dòng {i}", f"đáp {i}"] for i in range(50)]
    chunks = chunk_rows(sub, max_rows=20, overlap=2, header_rows=2)
    assert len(chunks) > 1
    for c in chunks:
        assert "TIÊU ĐỀ KHỐI" in c  # header lặp lại ở mọi chunk


def test_chunk_rows_covers_all_rows():
    sub = [["h"]] + [[f"dòng {i}"] for i in range(45)]
    chunks = chunk_rows(sub, max_rows=20, overlap=3, header_rows=1)
    merged = "\n".join(chunks)
    for i in range(45):
        assert f"dòng {i}" in merged


def test_grid_to_chunks_end_to_end():
    chunks = grid_to_chunks(GRID)
    merged = "\n".join(chunks)
    assert "Khách hỏi giá | Dạ váy bên em 350k ạ" in merged
    assert "Khách hỏi đổi trả | Dạ được đổi trong 7 ngày ạ" in merged
