"""Tầng truy cập Supabase (Postgres + pgvector) qua asyncpg.

Mọi SQL của hệ thống tập trung ở đây để dễ soát và đổi schema.
"""
from __future__ import annotations

import json
from typing import Any

import asyncpg
from pgvector.asyncpg import register_vector

from .config import settings

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await register_vector(conn)
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # statement_cache_size=0: Supabase pooler (pgbouncer transaction mode)
        # không hỗ trợ prepared statements.
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=5,
            init=_init_conn,
            statement_cache_size=0,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---------- shop & config ----------

async def ensure_shop(slug: str, name: str) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        insert into shops (slug, name) values ($1, $2)
        on conflict (slug) do update set name = excluded.name
        returning id
        """,
        slug,
        name,
    )
    return row["id"]


async def get_config(shop_id: int, key: str, default: Any = None) -> Any:
    pool = await get_pool()
    row = await pool.fetchrow(
        "select value from shop_config where shop_id=$1 and key=$2", shop_id, key
    )
    return row["value"] if row else default


async def set_config(shop_id: int, key: str, value: Any) -> None:
    pool = await get_pool()
    await pool.execute(
        """
        insert into shop_config (shop_id, key, value) values ($1, $2, $3)
        on conflict (shop_id, key) do update
          set value = excluded.value, updated_at = now()
        """,
        shop_id,
        key,
        value,
    )


# ---------- chống trùng webhook ----------

async def claim_update(channel: str, update_id: str) -> bool:
    """True nếu update CHƯA từng xử lý (và vừa được ghi nhận)."""
    pool = await get_pool()
    result = await pool.execute(
        "insert into processed_updates (channel, update_id) values ($1, $2) "
        "on conflict do nothing",
        channel,
        update_id,
    )
    return result.endswith("1")


# ---------- ingest & tri thức ----------

async def create_ingest_run(shop_id: int, source: str) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into ingest_runs (shop_id, source) values ($1, $2) returning id",
        shop_id,
        source,
    )
    return row["id"]


async def finish_ingest_run(
    run_id: int, status: str, stats: dict | None = None, error: str | None = None
) -> None:
    pool = await get_pool()
    await pool.execute(
        "update ingest_runs set status=$2, stats=$3, error=$4, finished_at=now() "
        "where id=$1",
        run_id,
        status,
        stats or {},
        error,
    )


async def activate_ingest_entries(
    shop_id: int, run_id: int, entries: list[dict]
) -> int:
    """Ghi các entry mới và thay thế bản sheet cũ trong CÙNG một transaction.

    entries: [{question, answer, intent, category, embedding}]
    Bản cũ chỉ bị 'superseded' khi run mới thành công -> ingest lỗi không mất dữ liệu.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.executemany(
                """
                insert into knowledge_entries
                  (shop_id, source, ingest_run_id, intent, category,
                   question, answer, embedding)
                values ($1, 'sheet', $2, $3, $4, $5, $6, $7)
                """,
                [
                    (
                        shop_id,
                        run_id,
                        e.get("intent"),
                        e.get("category"),
                        e["question"],
                        e["answer"],
                        e["embedding"],
                    )
                    for e in entries
                ],
            )
            await conn.execute(
                """
                update knowledge_entries
                   set status='superseded', deactivated_at=now()
                 where shop_id=$1 and source='sheet' and status='active'
                   and ingest_run_id is distinct from $2
                """,
                shop_id,
                run_id,
            )
    return len(entries)


async def search_knowledge(
    shop_id: int, embedding: Any, top_k: int = 6
) -> list[dict]:
    """Semantic search pgvector; similarity = 1 - cosine distance."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        select id, question, answer, intent, category, source,
               1 - (embedding <=> $1) as similarity
          from knowledge_entries
         where shop_id = $2 and status = 'active' and embedding is not null
         order by embedding <=> $1
         limit $3
        """,
        embedding,
        shop_id,
        top_k,
    )
    return [dict(r) for r in rows]


async def insert_taught_entry(
    shop_id: int,
    question: str,
    answer: str,
    embedding: Any,
    taught_by: str,
    approved_by: str,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        insert into knowledge_entries
          (shop_id, source, question, answer, embedding, taught_by, approved_by,
           intent, category)
        values ($1, 'taught', $2, $3, $4, $5, $6, 'taught', 'Câu nhân viên dạy')
        returning id
        """,
        shop_id,
        question,
        answer,
        embedding,
        taught_by,
        approved_by,
    )
    return row["id"]


# ---------- hội thoại ----------

async def get_or_create_conversation(
    shop_id: int, channel: str, external_user_id: str
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        insert into conversations (shop_id, channel, external_user_id, last_message_at)
        values ($1, $2, $3, now())
        on conflict (shop_id, channel, external_user_id)
          do update set last_message_at = now()
        returning id
        """,
        shop_id,
        channel,
        external_user_id,
    )
    return row["id"]


async def get_conversation_target(conversation_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "select channel, external_user_id from conversations where id=$1",
        conversation_id,
    )
    return dict(row) if row else None


async def log_message(
    conversation_id: int,
    role: str,
    content: str | None,
    meta: dict | None = None,
    media: dict | None = None,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into messages (conversation_id, role, content, meta, media) "
        "values ($1, $2, $3, $4, $5) returning id",
        conversation_id,
        role,
        content,
        meta or {},
        media,
    )
    return row["id"]


async def recent_messages(conversation_id: int, limit: int) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "select role, content from messages "
        "where conversation_id=$1 and content is not null and content <> '' "
        "order by id desc limit $2",
        conversation_id,
        limit,
    )
    return [dict(r) for r in reversed(rows)]


# ---------- câu khó & vòng học ----------

async def create_hard_question(
    shop_id: int, conversation_id: int, question: str
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into hard_questions (shop_id, conversation_id, question) "
        "values ($1, $2, $3) returning id",
        shop_id,
        conversation_id,
        question,
    )
    return row["id"]


async def set_hard_question_alert(hard_id: int, alert_message_id: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "update hard_questions set alert_message_id=$2 where id=$1",
        hard_id,
        alert_message_id,
    )


async def find_hard_question_by_alert(
    shop_id: int, alert_message_id: str
) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "select id, conversation_id, question, status from hard_questions "
        "where shop_id=$1 and alert_message_id=$2 order by id desc limit 1",
        shop_id,
        alert_message_id,
    )
    return dict(row) if row else None


async def mark_hard_question_answered(hard_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "update hard_questions set status='answered' where id=$1", hard_id
    )


async def create_pending_teaching(
    shop_id: int,
    question: str,
    answer: str,
    taught_by: str,
    conversation_id: int | None,
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into pending_teachings "
        "(shop_id, question, answer, taught_by, conversation_id) "
        "values ($1, $2, $3, $4, $5) returning id",
        shop_id,
        question,
        answer,
        taught_by,
        conversation_id,
    )
    return row["id"]


async def get_pending_teaching(teaching_id: int) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "select * from pending_teachings where id=$1", teaching_id
    )
    return dict(row) if row else None


async def resolve_pending_teaching(
    teaching_id: int, status: str, reviewed_by: str, knowledge_entry_id: int | None
) -> None:
    pool = await get_pool()
    await pool.execute(
        "update pending_teachings set status=$2, reviewed_by=$3, "
        "knowledge_entry_id=$4, reviewed_at=now() where id=$1",
        teaching_id,
        status,
        reviewed_by,
        knowledge_entry_id,
    )


# ---------- đơn hàng & ảnh ----------

async def create_order(
    shop_id: int, conversation_id: int, fields: dict, raw_text: str
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into orders (shop_id, conversation_id, fields, raw_text) "
        "values ($1, $2, $3, $4) returning id",
        shop_id,
        conversation_id,
        fields,
        raw_text,
    )
    return row["id"]


async def add_image_asset(
    shop_id: int, intent: str, file_id: str, caption: str, added_by: str
) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        "insert into image_assets (shop_id, intent, file_id, caption, added_by) "
        "values ($1, $2, $3, $4, $5) returning id",
        shop_id,
        intent,
        file_id,
        caption,
        added_by,
    )
    return row["id"]


async def images_for_intent(shop_id: int, intent: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "select file_id, url, caption from image_assets "
        "where shop_id=$1 and intent=$2 and status='active'",
        shop_id,
        intent,
    )
    return [dict(r) for r in rows]


# ---------- đo lường ----------

async def stats_summary(shop_id: int, days: int = 7) -> dict:
    pool = await get_pool()
    interval = f"{int(days)} days"
    row = await pool.fetchrow(
        f"""
        select
          (select count(*) from messages m
             join conversations c on c.id = m.conversation_id
            where c.shop_id=$1 and m.role='customer'
              and m.created_at > now() - interval '{interval}') as customer_messages,
          (select count(*) from messages m
             join conversations c on c.id = m.conversation_id
            where c.shop_id=$1 and m.role='bot'
              and m.created_at > now() - interval '{interval}') as bot_replies,
          (select count(*) from hard_questions
            where shop_id=$1
              and created_at > now() - interval '{interval}') as hard_questions,
          (select count(*) from orders
            where shop_id=$1
              and created_at > now() - interval '{interval}') as orders,
          (select count(*) from pending_teachings
            where shop_id=$1 and status='approved'
              and reviewed_at > now() - interval '{interval}') as taught_approved,
          (select count(*) from pending_teachings
            where shop_id=$1 and status='pending') as pending_review,
          (select count(*) from knowledge_entries
            where shop_id=$1 and status='active') as active_knowledge
        """,
        shop_id,
    )
    return dict(row)
