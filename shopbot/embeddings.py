"""Embeddings qua OpenAI (text-embedding-3-small, đa ngôn ngữ, rẻ)."""
from __future__ import annotations

from openai import AsyncOpenAI

from .config import settings

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed theo lô (API nhận tối đa ~2048 input/lần; ta cắt 100 cho an toàn)."""
    out: list[list[float]] = []
    for i in range(0, len(texts), 100):
        batch = [t[:6000] for t in texts[i : i + 100]]
        resp = await _get_client().embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=settings.embedding_dim,
        )
        out.extend(d.embedding for d in resp.data)
    return out


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]
