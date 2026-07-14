"""Tải Google Sheet public về dạng lưới (grid) thô.

Chấp nhận:
  - Link edit:  https://docs.google.com/spreadsheets/d/<ID>/edit#gid=<GID>
  - Link export: .../export?format=csv&gid=<GID>
Nhiều tab = nhiều URL (mỗi URL 1 gid), cách nhau dấu phẩy trong SHEET_URLS.
"""
from __future__ import annotations

import csv
import io
import re

import httpx

_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")
_GID_RE = re.compile(r"[#?&]gid=(\d+)")


def to_csv_export_url(url: str) -> str:
    url = url.strip()
    if "export?format=csv" in url or url.endswith(".csv"):
        return url
    m = _SHEET_ID_RE.search(url)
    if not m:
        raise ValueError(f"Không nhận diện được link Google Sheet: {url}")
    sheet_id = m.group(1)
    gid_m = _GID_RE.search(url)
    gid = gid_m.group(1) if gid_m else "0"
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export"
        f"?format=csv&gid={gid}"
    )


def parse_grid(csv_text: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(csv_text))
    return [[cell.strip() for cell in row] for row in reader]


async def fetch_grid(url: str) -> list[list[str]]:
    export_url = to_csv_export_url(url)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(export_url)
        resp.raise_for_status()
    return parse_grid(resp.text)
