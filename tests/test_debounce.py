import asyncio

import pytest

from shopbot.telegram.debounce import MessageBuffer


@pytest.mark.asyncio
async def test_merges_burst_into_one_flush():
    flushed: list[tuple[str, str]] = []

    async def cb(chat_id: str, text: str) -> None:
        flushed.append((chat_id, text))

    buf = MessageBuffer(0.05, cb)
    buf.add("1", "chị ơi")
    await asyncio.sleep(0.01)
    buf.add("1", "váy đó")
    await asyncio.sleep(0.01)
    buf.add("1", "nhiêu")
    await asyncio.sleep(0.15)

    assert flushed == [("1", "chị ơi\nváy đó\nnhiêu")]


@pytest.mark.asyncio
async def test_separate_chats_do_not_merge():
    flushed: list[tuple[str, str]] = []

    async def cb(chat_id: str, text: str) -> None:
        flushed.append((chat_id, text))

    buf = MessageBuffer(0.05, cb)
    buf.add("1", "a")
    buf.add("2", "b")
    await asyncio.sleep(0.15)
    assert sorted(flushed) == [("1", "a"), ("2", "b")]


@pytest.mark.asyncio
async def test_flush_now_delivers_pending_immediately():
    flushed: list[str] = []

    async def cb(chat_id: str, text: str) -> None:
        flushed.append(text)

    buf = MessageBuffer(5.0, cb)  # delay dài — không thể tự flush trong test
    buf.add("1", "tin đang chờ")
    await buf.flush_now("1")
    assert flushed == ["tin đang chờ"]


@pytest.mark.asyncio
async def test_empty_buffer_flush_is_noop():
    calls: list[str] = []

    async def cb(chat_id: str, text: str) -> None:
        calls.append(text)

    buf = MessageBuffer(0.01, cb)
    await buf.flush_now("1")
    assert calls == []
