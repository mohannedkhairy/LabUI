"""Feature-level checks shared by setup, launchers, and the health API.

Imports test real entrypoints, not just package presence. They do not download
or load model weights. Model downloads still happen on first use.
"""
from __future__ import annotations

import importlib
import sqlite3

FEATURES = {
    "application": (
        ("fastapi", "FastAPI"), ("uvicorn", "run"), ("jinja2", "Environment"),
        ("multipart", None), ("aiofiles", None), ("pydantic_settings", "BaseSettings"),
        ("httpx", "Client"), ("requests", "Session"), ("yaml", "safe_load"),
        ("typer", "Typer"), ("rich", None),
    ),
    "retrieval": (
        ("torch", None), ("numpy", None), ("sqlite_vec", "load"),
        ("sentence_transformers", "SentenceTransformer"),
        ("sentence_transformers", "CrossEncoder"), ("rank_bm25", "BM25Okapi"), ("tqdm", "tqdm"),
    ),
    "pdf_ingestion": (("docling.document_converter", "DocumentConverter"), ("fitz", "open")),
    "equipment_files": (("PIL.Image", "open"), ("PIL.ImageOps", "exif_transpose"), ("pymupdf", "open")),
    "web_search": (("ddgs", "DDGS"),),
    "journals": (("feedparser", "parse"), ("apscheduler.schedulers.background", "BackgroundScheduler"),
                 ("qdrant_client", "QdrantClient"), ("peft", None)),
    "graph_extraction": (("gliner", "GLiNER"), ("spacy", "load"), ("en_core_web_sm", "load")),
}
EVALUATION = (("ragas", "evaluate"), ("datasets", "Dataset"),
              ("langchain_community.chat_models", "ChatOllama"),
              ("langchain_community.embeddings", "OllamaEmbeddings"))


class RuntimeDependencyError(RuntimeError):
    pass


def check_feature(name: str) -> dict:
    entries = EVALUATION if name == "evaluation" else FEATURES[name]
    issues = []
    for module_name, attribute in entries:
        try:
            module = importlib.import_module(module_name)
            if attribute:
                getattr(module, attribute)
        except Exception as exc:
            issues.append(f"{module_name}: {type(exc).__name__}: {exc}")
    if name == "retrieval" and not issues:
        try:
            from sqlite_vec import load
            with sqlite3.connect(":memory:") as connection:
                connection.enable_load_extension(True)
                load(connection)
                connection.enable_load_extension(False)
                connection.execute("SELECT vec_version()")
                connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
        except Exception as exc:
            issues.append(f"SQLite extensions: {type(exc).__name__}: {exc}")
    return {"ready": not issues, "issues": issues}


def runtime_report(include_evaluation: bool = False) -> dict:
    features = {name: check_feature(name) for name in FEATURES}
    if include_evaluation:
        features["evaluation"] = check_feature("evaluation")
    return {"ready": all(feature["ready"] for feature in features.values()), "features": features}


def require_feature(name: str) -> None:
    status = check_feature(name)
    if not status["ready"]:
        setup = "./setup.sh --with-evaluation" if name == "evaluation" else "./setup.sh"
        raise RuntimeDependencyError(
            f"{name} is unavailable in this Python environment. Run {setup} from the LabUI directory. "
            + " | ".join(status["issues"])
        )
