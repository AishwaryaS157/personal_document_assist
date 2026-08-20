-- Migration 002: OR semantics for the full-text arm
--
-- plainto_tsquery ANDs every term, so a passage missing any single word was
-- excluded outright. Measured on the fixture corpus, the keyword arm reached
-- only Recall@5 12.5% and RRF was therefore identical to dense-only search.
-- Both functions are replaced together so the eval keeps matching production.
--
-- Safe on an existing database: CREATE OR REPLACE only, no tables touched,
-- nothing dropped, no re-embedding needed. Paste this whole file into the
-- Supabase SQL editor.

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
  with q as (
    -- plainto_tsquery ANDs every term, so a passage missing any one word is
    -- excluded outright however well it matches otherwise. Natural-language
    -- questions rarely satisfy the full conjunction, which left this arm
    -- contributing almost nothing (measured: Recall@5 12.5%). OR the lexemes
    -- instead and let ts_rank order by how well each passage matches.
    select replace(
             plainto_tsquery('english', query_text)::text, ' & ', ' | '
           )::tsquery as tsq
  ),
  vector_ranked as (
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
      dc.id,
      row_number() over (order by ts_rank(dc.fts, q.tsq) desc) as rank
    from document_chunks dc, q
    where dc.user_id = user_id_filter
      and dc.fts @@ q.tsq
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

-- Evaluation-only variant of search_chunks. Same two rankers and same fusion,
-- but it exposes each arm's rank instead of collapsing to the fused score, so
-- the eval harness can score dense-only, fts-only and RRF independently and
-- show whether fusion actually beats either arm on its own.
--
-- Returns every candidate (not a top-k slice): the dense arm's top-k is not
-- generally a subset of the fused top-k, so the caller re-sorts per arm.
create or replace function search_chunks_eval(
  query_embedding  vector(384),
  query_text       text,
  user_id_filter   uuid,
  candidate_depth  int default 50
)
returns table (
  id          uuid,
  doc_id      uuid,
  content     text,
  chunk_index int,
  filename    text,
  dense_rank  int,
  fts_rank    int,
  rrf_score   float
)
language sql stable
as $$
  with q as (
    -- Must match search_chunks exactly, or the eval stops describing production.
    select replace(
             plainto_tsquery('english', query_text)::text, ' & ', ' | '
           )::tsquery as tsq
  ),
  vector_ranked as (
    select
      id,
      row_number() over (order by embedding <=> query_embedding) as rank
    from document_chunks
    where user_id = user_id_filter
      and embedding is not null
    limit candidate_depth
  ),
  fts_ranked as (
    select
      dc.id,
      row_number() over (order by ts_rank(dc.fts, q.tsq) desc) as rank
    from document_chunks dc, q
    where dc.user_id = user_id_filter
      and dc.fts @@ q.tsq
    limit candidate_depth
  ),
  fused as (
    select
      coalesce(v.id, f.id) as id,
      v.rank               as dense_rank,
      f.rank               as fts_rank,
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
    fused.dense_rank::int,
    fused.fts_rank::int,
    fused.score
  from fused
  join document_chunks dc on fused.id = dc.id
  order by fused.score desc;
$$;
