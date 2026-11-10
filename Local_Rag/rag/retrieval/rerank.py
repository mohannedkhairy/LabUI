"""Configured local cross encoder or LM Studio relevance model."""
import sys
from pathlib import Path
from typing import Sequence

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import RERANKER_MODEL, RERANKER_CACHE, RERANK_PROVIDER, RERANK_BASE_URL

def _detect_device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


_DEVICE = 'remote' if RERANK_PROVIDER == 'lmstudio' else _detect_device()


def load_reranker():
    if RERANK_PROVIDER == 'lmstudio':
        from retrieval.remote import RemoteReranker
        model = RemoteReranker(RERANK_BASE_URL, RERANKER_MODEL)
        scores = model.predict([('What gas was used?', 'The experiment used nitrogen gas.'),
                                ('What gas was used?', 'The recipe contains flour and butter.')])
        if scores[0] <= scores[1]:
            raise ValueError('Remote reranker failed its relevance readiness check')
        return model
    if RERANK_PROVIDER != 'local':
        raise ValueError(f'Unknown reranker provider: {RERANK_PROVIDER}')
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(
        RERANKER_MODEL,
        max_length=512,
        device=_DEVICE,
        cache_folder=str(RERANKER_CACHE),
    )
    return model


def rerank(model, query: str, chunks: list[dict], top_n: int) -> list[dict]:
    """
    Rerank chunks using the cross-encoder. Returns top_n chunks sorted by score.
    Each chunk dict must have a 'text' field.
    """
    if not chunks:
        return []

    pairs = [(query, f"{c.get('title', '')}\n{c['text']}") for c in chunks]
    scores = model.predict(pairs, show_progress_bar=False)

    scored = sorted(zip(scores, chunks), key=lambda x: -x[0])
    return [c for _, c in scored[:top_n]]
