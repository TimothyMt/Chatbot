"""Chạy ingest từ terminal: python scripts/ingest.py [sheet_url,...]"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from shopbot import db  # noqa: E402
from shopbot.config import settings  # noqa: E402
from shopbot.ingest.run import run_ingest  # noqa: E402


async def main() -> None:
    urls = sys.argv[1] if len(sys.argv) > 1 else None
    shop_id = await db.ensure_shop(settings.shop_slug, settings.shop_name)
    stats = await run_ingest(shop_id, urls)
    print(f"OK: {stats}")
    await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
