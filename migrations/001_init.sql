-- Schema Supabase cho chatbot CSKH.
-- Chạy bằng: python scripts/migrate.py (idempotent, theo dõi qua schema_migrations)

create extension if not exists vector;

-- Shop + config: mọi thứ theo shop là DATA, không hardcode
create table if not exists shops (
    id          bigserial primary key,
    slug        text not null unique,
    name        text not null,
    created_at  timestamptz not null default now()
);

create table if not exists shop_config (
    shop_id     bigint not null references shops(id),
    key         text not null,
    value       jsonb not null,
    updated_at  timestamptz not null default now(),
    primary key (shop_id, key)
);

-- Versioning tri thức: mỗi lần nạp sheet là 1 run, rollback được
create table if not exists ingest_runs (
    id          bigserial primary key,
    shop_id     bigint not null references shops(id),
    source      text,
    status      text not null default 'running',  -- running | succeeded | failed
    stats       jsonb not null default '{}',
    error       text,
    started_at  timestamptz not null default now(),
    finished_at timestamptz
);

-- Kho tri thức: Q&A từ sheet hoặc do nhân viên dạy (đã duyệt)
create table if not exists knowledge_entries (
    id             bigserial primary key,
    shop_id        bigint not null references shops(id),
    source         text not null,                 -- 'sheet' | 'taught'
    ingest_run_id  bigint references ingest_runs(id),
    intent         text,
    category       text,
    question       text not null,
    answer         text not null,
    status         text not null default 'active', -- active | superseded | disabled
    taught_by      text,
    approved_by    text,
    embedding      vector(1536),
    created_at     timestamptz not null default now(),
    deactivated_at timestamptz
);
create index if not exists knowledge_entries_active_idx
    on knowledge_entries (shop_id, status);
create index if not exists knowledge_entries_embedding_idx
    on knowledge_entries using hnsw (embedding vector_cosine_ops);

-- Hàng đợi duyệt câu học
create table if not exists pending_teachings (
    id                 bigserial primary key,
    shop_id            bigint not null references shops(id),
    question           text not null,
    answer             text not null,
    taught_by          text,
    conversation_id    bigint,
    status             text not null default 'pending', -- pending | approved | rejected
    reviewed_by        text,
    knowledge_entry_id bigint references knowledge_entries(id),
    created_at         timestamptz not null default now(),
    reviewed_at        timestamptz
);

-- Hội thoại + log đầy đủ (bộ nhớ ngữ cảnh và đo lường dùng chung bảng messages)
create table if not exists conversations (
    id               bigserial primary key,
    shop_id          bigint not null references shops(id),
    channel          text not null,
    external_user_id text not null,
    created_at       timestamptz not null default now(),
    last_message_at  timestamptz,
    unique (shop_id, channel, external_user_id)
);

create table if not exists messages (
    id              bigserial primary key,
    conversation_id bigint not null references conversations(id),
    role            text not null,              -- customer | bot | staff
    content         text,
    media           jsonb,
    -- meta: source, similarity, intent, used_entry_ids, rewritten_query,
    --       latency_ms, model... phục vụ đo lường + truy vết "trả lời từ đâu"
    meta            jsonb not null default '{}',
    created_at      timestamptz not null default now()
);
create index if not exists messages_conversation_idx
    on messages (conversation_id, id desc);
create index if not exists messages_created_idx on messages (created_at);

-- Câu khó: bot không chắc -> báo nhân sự; alert_message_id để map reply của
-- nhân viên trong nhóm về đúng khách + đúng câu hỏi (vòng học)
create table if not exists hard_questions (
    id               bigserial primary key,
    shop_id          bigint not null references shops(id),
    conversation_id  bigint not null references conversations(id),
    question         text not null,
    alert_message_id text,
    status           text not null default 'open', -- open | answered
    created_at       timestamptz not null default now()
);
create index if not exists hard_questions_alert_idx
    on hard_questions (shop_id, alert_message_id);

-- Đơn hàng: CHỈ chứa field khách tự cung cấp (không bịa)
create table if not exists orders (
    id              bigserial primary key,
    shop_id         bigint not null references shops(id),
    conversation_id bigint references conversations(id),
    fields          jsonb not null,
    raw_text        text,
    status          text not null default 'new',
    created_at      timestamptz not null default now()
);

-- Ảnh theo intent (bảng size, STK/QR, mẫu...); lưu telegram file_id
create table if not exists image_assets (
    id         bigserial primary key,
    shop_id    bigint not null references shops(id),
    intent     text not null,
    file_id    text,
    url        text,
    caption    text,
    status     text not null default 'active',
    added_by   text,
    created_at timestamptz not null default now()
);
create index if not exists image_assets_intent_idx on image_assets (shop_id, intent);

-- Chống trùng webhook (retry cùng update_id)
create table if not exists processed_updates (
    channel      text not null,
    update_id    text not null,
    processed_at timestamptz not null default now(),
    primary key (channel, update_id)
);
