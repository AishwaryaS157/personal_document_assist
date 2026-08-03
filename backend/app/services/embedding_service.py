import os
from pathlib import Path
from typing import List

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
ONNX_FILENAME = "onnx/model.onnx"
CACHE_DIR = Path(os.environ.get("MODEL_CACHE_DIR", "/tmp/model_cache"))
MAX_SEQ_LENGTH = 256

_session: ort.InferenceSession | None = None
_tokenizer: Tokenizer | None = None


def _load() -> None:
    global _session, _tokenizer
    if _session is not None:
        return

    onnx_path = hf_hub_download(MODEL_REPO, ONNX_FILENAME, cache_dir=str(CACHE_DIR))
    tokenizer_path = hf_hub_download(MODEL_REPO, "tokenizer.json", cache_dir=str(CACHE_DIR))

    _tokenizer = Tokenizer.from_file(tokenizer_path)
    _tokenizer.enable_padding()
    _tokenizer.enable_truncation(max_length=MAX_SEQ_LENGTH)

    _session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])


def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask = attention_mask[..., None].astype(np.float32)
    summed = (token_embeddings * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), a_min=1e-9, a_max=None)
    return summed / counts


def get_embeddings(texts: List[str]) -> List[List[float]]:
    _load()

    encodings = _tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    outputs = _session.run(
        None,
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        },
    )
    token_embeddings = outputs[0]

    pooled = _mean_pool(token_embeddings, attention_mask)
    norm = np.linalg.norm(pooled, axis=1, keepdims=True)
    normalized = pooled / np.clip(norm, a_min=1e-9, a_max=None)
    return normalized.tolist()


def get_embedding(text: str) -> List[float]:
    return get_embeddings([text])[0]
