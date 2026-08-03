create extension if not exists vector;

drop table if exists document_chunks cascade;
drop table if exists documents cascade;
drop table if exists users cascade;

create table users (
  id            uuid primary key default gen_random_uuid(),
  email         text unique not null,
  password_hash text not null,
  created_at    timestamptz default now()
);

create table documents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references users(id) not null,
  filename    text not null,
  chunk_count int  not null,
  created_at  timestamptz default now()
);

create table document_chunks (
  id          uuid primary key default gen_random_uuid(),
  doc_id      uuid references documents(id) on delete cascade not null,
  user_id     uuid references users(id) not null,
  filename    text not null,
  content     text not null,
  chunk_index int  not null,
  embedding   vector(384),
  fts         tsvector generated always as (to_tsvector('english', content)) stored
);

create index on document_chunks using hnsw (embedding vector_cosine_ops);
create index on document_chunks using gin(fts);

alter table users           disable row level security;
alter table documents       disable row level security;
alter table document_chunks disable row level security;

create or replace function search_chunks(
  query_embedding  vector(384),
  query_text       text,
  user_id_filter   uuid,
  match_count      int default 5
)
returns table (
  id          uuid,
  doc_id      uuid,
  content     text,
  chunk_index int,
  filename    text,
  similarity  float
)
language sql stable
as $$
  with vector_ranked as (
    select
      id,
      row_number() over (order by embedding <=> query_embedding) as rank
    from document_chunks
    where user_id = user_id_filter
      and embedding is not null
    limit 50
  ),
  fts_ranked as (
    select
      id,
      row_number() over (order by ts_rank(fts, plainto_tsquery('english', query_text)) desc) as rank
    from document_chunks
    where user_id = user_id_filter
      and fts @@ plainto_tsquery('english', query_text)
    limit 50
  ),
  rrf as (
    select
      coalesce(v.id, f.id) as id,
      coalesce(1.0 / (60 + v.rank), 0.0) + coalesce(1.0 / (60 + f.rank), 0.0) as score
    from vector_ranked v
    full outer join fts_ranked f on v.id = f.id
  )
  select
    dc.id,
    dc.doc_id,
    dc.content,
    dc.chunk_index,
    dc.filename,
    rrf.score as similarity
  from rrf
  join document_chunks dc on rrf.id = dc.id
  order by rrf.score desc
  limit match_count;
$$;
