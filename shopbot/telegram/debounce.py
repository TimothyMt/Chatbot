"""Gộp tin nhắn dồn dập của khách thành một lượt xử lý.

Khách VN hay nhắn nhiều tin ngắn liên tiếp ("chị ơi" / "váy đó" / "nhiêu").
Mỗi tin mới reset đồng hồ; hết N giây im lặng thì flush cả cụm một lần.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

FlushCallback = Callable[[str, str], Awaitable[None]]  # (chat_id, merged_text)


class MessageBuffer:
    def __init__(self, delay_seconds: float, flush_cb: FlushCallback) -> None:
        self._delay = delay_seconds
        self._flush_cb = flush_cb
        self._buffers: dict[str, list[str]] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def add(self, chat_id: str, text: str) -> None:
        self._buffers.setdefault(chat_id, []).append(text)
        old = self._tasks.pop(chat_id, None)
        if old:
            old.cancel()
        self._tasks[chat_id] = asyncio.create_task(self._wait_and_flush(chat_id))

    async def flush_now(self, chat_id: str) -> None:
        """Flush ngay (vd khi khách gửi ảnh, cần xử lý text đang chờ trước)."""
        task = self._tasks.pop(chat_id, None)
        if task:
            task.cancel()
        await self._flush(chat_id)

    async def _wait_and_flush(self, chat_id: str) -> None:
        try:
            await asyncio.sleep(self._delay)
        except asyncio.CancelledError:
            return
        self._tasks.pop(chat_id, None)
        await self._flush(chat_id)

    async def _flush(self, chat_id: str) -> None:
        texts = self._buffers.pop(chat_id, [])
        merged = "\n".join(t for t in texts if t.strip()).strip()
        if merged:
            await self._flush_cb(chat_id, merged)
