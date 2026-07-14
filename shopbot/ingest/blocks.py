"""Cắt lưới bảng tính lộn xộn thành các đoạn văn bản cho LLM trích xuất.

Chiến lược cấu-trúc-bất-khả-tri (không cần khai báo cột):
1. Tách NHÓM CỘT: các khối kịch bản thường xếp cạnh nhau, ngăn bởi >=1 cột
   trống hoàn toàn -> tách theo cột trống.
2. Trong mỗi nhóm cột, cắt CỬA SỔ DÒNG chồng lấn (chunk) để vừa ngân sách
   token; vài dòng đầu nhóm được nhắc lại ở mọi chunk làm ngữ cảnh tiêu đề.
Phần hiểu ngữ nghĩa (đâu là Q&A, đâu là nhiễu) do LLM đảm nhiệm.
"""
from __future__ import annotations

Grid = list[list[str]]


def _width(grid: Grid) -> int:
    return max((len(r) for r in grid), default=0)


def split_column_groups(grid: Grid) -> list[Grid]:
    """Tách lưới thành các lưới con theo cột trống hoàn toàn."""
    width = _width(grid)
    if width == 0:
        return []
    non_empty = [
        any(r[c].strip() for r in grid if c < len(r)) for c in range(width)
    ]
    groups: list[tuple[int, int]] = []
    start: int | None = None
    for c in range(width):
        if non_empty[c] and start is None:
            start = c
        elif not non_empty[c] and start is not None:
            groups.append((start, c))
            start = None
    if start is not None:
        groups.append((start, width))

    out: list[Grid] = []
    for lo, hi in groups:
        sub = []
        for row in grid:
            cells = [row[c] if c < len(row) else "" for c in range(lo, hi)]
            if any(c.strip() for c in cells):
                sub.append(cells)
        if sub:
            out.append(sub)
    return out


def render_rows(rows: Grid) -> str:
    lines = []
    for row in rows:
        cells = [c for c in row if c.strip()]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def chunk_rows(
    subgrid: Grid, max_rows: int = 30, overlap: int = 4, header_rows: int = 2
) -> list[str]:
    """Cắt lưới con thành chunk văn bản; mỗi chunk kèm vài dòng đầu làm header."""
    if not subgrid:
        return []
    header = subgrid[:header_rows]
    body = subgrid[header_rows:]
    if not body:
        return [render_rows(header)]

    chunks: list[str] = []
    step = max(1, max_rows - overlap)
    for i in range(0, len(body), step):
        window = body[i : i + max_rows]
        text = render_rows(header) + "\n" + render_rows(window)
        chunks.append(text.strip())
        if i + max_rows >= len(body):
            break
    return chunks


def grid_to_chunks(grid: Grid, max_rows: int = 30) -> list[str]:
    chunks: list[str] = []
    for sub in split_column_groups(grid):
        chunks.extend(chunk_rows(sub, max_rows=max_rows))
    return [c for c in chunks if c]
