"""Chạy migration SQL theo thứ tự, idempotent (theo dõi qua schema_migrations).

Dùng: DATABASE_URL=postgres://... python scripts/migrate.py
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

from shopbot.config import settings  # noqa: E402

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


async def main() -> None:
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        await conn.execute(
            "create table if not exists schema_migrations ("
            "  name text primary key, applied_at timestamptz not null default now())"
        )
        applied = {
            r["name"] for r in await conn.fetch("select name from schema_migrations")
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                print(f"bỏ qua (đã chạy): {path.name}")
                continue
            print(f"chạy: {path.name}")
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "insert into schema_migrations (name) values ($1)", path.name
                )
        print("xong.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
