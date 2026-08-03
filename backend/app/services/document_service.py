import io
from pathlib import Path
from typing import List, Dict, Any

import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.database import get_supabase
from app.services.embedding_service import get_embedding as _get_embedding

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


def _chunk_text(text: str) -> List[str]:
    return _splitter.split_text(text)


def _extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = [p.extract_text() for p in pdf.pages if p.extract_text()]
        return "\n\n".join(pages)
    return file_bytes.decode("utf-8", errors="replace")


def ingest_document(file_bytes: bytes, filename: str, user_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    text = _extract_text(file_bytes, filename)
    chunks = _chunk_text(text)
    if not chunks:
        raise ValueError("No text could be extracted from the document.")

    doc = supabase.table("documents").insert({
        "user_id": user_id,
        "filename": filename,
        "chunk_count": len(chunks),
    }).execute()
    doc_id = doc.data[0]["id"]

    rows = []
    for i, chunk in enumerate(chunks):
        embedding = _get_embedding(chunk)
        rows.append({
            "doc_id": doc_id,
            "user_id": user_id,
            "filename": filename,
            "content": chunk,
            "chunk_index": i,
            "embedding": embedding,
        })

    supabase.table("document_chunks").insert(rows).execute()
    return {"id": doc_id, "filename": filename, "chunk_count": len(chunks)}


def list_documents(user_id: str) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    result = (
        supabase.table("documents")
        .select("id, filename, chunk_count, created_at")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return result.data


def delete_document(doc_id: str, user_id: str) -> bool:
    supabase = get_supabase()
    result = (
        supabase.table("documents")
        .delete()
        .eq("id", doc_id)
        .eq("user_id", user_id)
        .execute()
    )
    return len(result.data) > 0


def search_documents(query: str, user_id: str, n_results: int = 5) -> List[Dict[str, Any]]:
    supabase = get_supabase()
    query_embedding = _get_embedding(query)
    result = supabase.rpc("search_chunks", {
        "query_embedding": query_embedding,
        "query_text": query,
        "user_id_filter": user_id,
        "match_count": n_results,
    }).execute()

    return [
        {
            "content": row["content"],
            "filename": row["filename"],
            "doc_id": row["doc_id"],
            "chunk_index": row["chunk_index"],
            "score": row.get("similarity", 0),
        }
        for row in result.data
    ]
