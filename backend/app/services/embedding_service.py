import os
import httpx

HF_API_URL = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"


def get_embeddings(texts: list[str]) -> list[list[float]]:
    headers = {"Content-Type": "application/json"}
    token = os.getenv("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=120) as client:
        res = client.post(
            HF_API_URL,
            headers=headers,
            json={"inputs": texts, "options": {"wait_for_model": True}},
        )
        res.raise_for_status()
        return res.json()


def get_embedding(text: str) -> list[float]:
    return get_embeddings([text])[0]
