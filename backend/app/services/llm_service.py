import json
import os
from typing import AsyncGenerator, List, Dict, Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = """You are a helpful personal document assistant. You answer questions based on the documents the user has uploaded.

When answering:
- Base your answers on the provided document excerpts
- If the answer is not in the documents, say so clearly
- Be concise and accurate
- Cite information from the sources when relevant"""

MODEL_NAME = "gemini-2.5-flash"
CITATION_THRESHOLD = 0.016
MAX_SOURCES_IN_CONTEXT = 5

_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _build_context(sources: List[Dict[str, Any]]) -> str:
    parts = [
        f"[Source {i} - {s['filename']} (chunk {s['chunk_index']})]\n{s['content']}"
        for i, s in enumerate(sources[:MAX_SOURCES_IN_CONTEXT], 1)
    ]
    return "\n\n---\n\n".join(parts)


async def stream_chat(
    message: str, sources: List[Dict[str, Any]]
) -> AsyncGenerator[str, None]:
    max_score = max((s["score"] for s in sources), default=0)
    display_sources = sources if max_score >= CITATION_THRESHOLD else []

    yield json.dumps({"type": "sources", "data": display_sources}) + "\n"

    if not display_sources:
        answer = (
            "I couldn't find any relevant information in your documents to answer this question.\n\n"
            "Try uploading documents that contain information about your query, or rephrase your question."
        )
        yield json.dumps({"type": "text", "data": answer}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"
        return

    user_message = f"""Here are relevant excerpts from your documents:

{_build_context(display_sources)}

---

User question: {message}"""

    try:
        stream = await _client.aio.models.generate_content_stream(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        )
        async for chunk in stream:
            if chunk.text:
                yield json.dumps({"type": "text", "data": chunk.text}) + "\n"
    except Exception as e:
        yield json.dumps({"type": "error", "data": str(e)}) + "\n"
        return

    yield json.dumps({"type": "done"}) + "\n"
