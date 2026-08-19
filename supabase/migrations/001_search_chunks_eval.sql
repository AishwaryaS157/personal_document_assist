-- Migration 001: add search_chunks_eval
-- Safe to run on an existing database: creates one function, touches no
-- tables and drops nothing. Paste this whole file into the Supabase SQL
-- editor. Do NOT paste schema.sql there -- it begins with drop table.

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
  with vector_ranked as (
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
      id,
      row_number() over (order by ts_rank(fts, plainto_tsquery('english', query_text)) desc) as rank
    from document_chunks
    where user_id = user_id_filter
      and fts @@ plainto_tsquery('english', query_text)
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
