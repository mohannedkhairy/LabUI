"""Local or LM Studio embeddings for paper search, indexing and saved memory.

Vector size follows the configured model. All vectors are L2 normalized; remote
Qwen queries receive an instruction while documents retain title/section text.
"""
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
from retrieval.remote import RemoteEncoder

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import EMBED_MODEL_BASE, EMBED_BATCH_SIZE, EMBED_DIM, EMBED_PROVIDER, EMBED_BASE_URL, EMBED_QUERY_INSTRUCTION


def _detect_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


_DEVICE = 'remote' if EMBED_PROVIDER == 'lmstudio' else _detect_device()


def load_embed_model():
    """Return (None, encoder) for the configured provider.

    First element is None (no separate tokenizer needed) to preserve the
    (tokenizer, model) tuple shape that existing call sites unpack.
    """
    if EMBED_PROVIDER == 'lmstudio':
        model = RemoteEncoder(EMBED_BASE_URL, EMBED_MODEL_BASE, EMBED_DIM, EMBED_QUERY_INSTRUCTION)
        model.encode(['Research retrieval readiness check.'])
        return None, model
    if EMBED_PROVIDER != 'local':
        raise ValueError(f'Unknown embedding provider: {EMBED_PROVIDER}')
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBED_MODEL_BASE, device=_DEVICE)
    # A smaller test model must retain its real positional limit.
    model.max_seq_length = min(8192, model.max_seq_length)
    actual_dim = model.get_sentence_embedding_dimension()
    if actual_dim != EMBED_DIM:
        raise ValueError(f"RAG_EMBED_DIM={EMBED_DIM} but {EMBED_MODEL_BASE} produces {actual_dim} dimensions")
    return None, model


def embed_texts(
    tokenizer,
    model,
    texts: Sequence[str],
    titles: Sequence[str] | None = None,
) -> np.ndarray:
    """Embed documents as float32 (N, EMBED_DIM)."""
    if not texts:
        return np.zeros((0, EMBED_DIM), dtype=np.float32)
    vecs = model.encode(
        list(texts),
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vecs.astype(np.float32)


def embed_query(tokenizer, model, query: str) -> np.ndarray:
    """Embed a query with the configured model's query formatting."""
    if isinstance(model, RemoteEncoder):
        return model.encode_query(query)
    vec = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )[0]
    return vec.astype(np.float32)
