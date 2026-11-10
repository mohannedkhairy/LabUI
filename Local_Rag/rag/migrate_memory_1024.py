#!/usr/bin/env python3
"""Repair memory vectors for the configured embedder (legacy command name).

Uses the same transactional repair as startup. Existing text and conversations
are preserved, including when encoding fails.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import MEMORY_DB_PATH, EMBED_DIM
from retrieval.embed import load_embed_model
from memory import init_db, repair_vector_index


def main():
    if not MEMORY_DB_PATH.exists():
        print("[mem] no memory.db — nothing to migrate")
        return
    init_db()
    tokenizer, model = load_embed_model()
    count = repair_vector_index(tokenizer, model)
    print(f"[mem] memory index ready at {EMBED_DIM} dimensions; restored {count} vectors")


if __name__ == "__main__":
    main()
