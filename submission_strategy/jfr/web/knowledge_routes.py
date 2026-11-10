"""Research-map API and bounded, resumable local findings jobs."""

from __future__ import annotations

import csv
import io
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from retrieval import knowledge as kg

router = APIRouter(prefix="/api/rag/knowledge", tags=["knowledge"])
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="research-map")
_lock = threading.Lock()
_cancel = threading.Event()
_state = {
    "running": False,
    "kind": None,
    "done": 0,
    "total": 0,
    "message": "",
    "error": None,
}


def update(**values):
    with _lock:
        _state.update(values)


def job_state():
    with _lock:
        return dict(_state)


def _run(kind, values):
    try:
        if kind == "index":
            stats = kg.build_index(
                progress=lambda done, total: update(
                    done=done, total=total, message=f"Mapping paper {done} of {total}"
                )
            )
            message = f"Map updated: {stats['mapped_papers']} papers connected through {stats['topics']} topics."
        else:
            from ingest.extract_findings import extract_findings

            from jfr.web.rag_routes import OLLAMA_BASE_URL, resolve_gen_model

            model = resolve_gen_model()
            stats = extract_findings(
                model,
                OLLAMA_BASE_URL,
                **values,
                stop=_cancel.is_set,
                progress=lambda s: update(
                    done=s["checked"],
                    total=s["total"],
                    message=f"Checked {s['checked']}/{s['total']} passages · {s['accepted']} findings · {s['rejected']} rejected",
                ),
            )
            prefix = "Stopped after" if stats.get("cancelled") else "Finished:"
            message = f"{prefix} {stats['checked']} passages, {stats['accepted']} source-checked findings; {stats['remaining']} passages remain."
        update(running=False, message=message, result=stats)
    except Exception as exc:  # noqa: BLE001 -- publish worker errors instead of leaving a stuck running job
        update(
            running=False,
            error=str(exc),
            message="Update stopped. Saved work is retained; retry to continue.",
        )


def start_job(kind, values):
    with _lock:
        if _state["running"]:
            raise HTTPException(409, "A research-map update is already running.")
        _cancel.clear()
        _state.update(
            running=True,
            kind=kind,
            done=0,
            total=0,
            error=None,
            result=None,
            message="Starting…",
        )
    try:
        _executor.submit(_run, kind, values)
    except Exception:
        update(running=False)
        raise
    return {"status": "started", "job": job_state()}


Year = Annotated[int | None, Query(ge=1600, le=2200)]


def validate_scope(category, year_from, year_to):
    if category and category not in kg.CATEGORY_COLORS:
        raise HTTPException(422, "Unknown topic category.")
    if year_from and year_to and year_from > year_to:
        raise HTTPException(422, "The first year must be before the last year.")


@router.get("/status")
def status():
    return {
        **kg.status(),
        "job": job_state(),
        "categories": [c for c in kg.CATEGORY_COLORS if c != "Paper"],
    }


@router.get("")
def research_map(
    q: str = Query("", max_length=200),
    focus: str = Query("", max_length=350),
    category: str = "",
    year_from: Year = None,
    year_to: Year = None,
    min_papers: int = Query(2, ge=1, le=100),
    limit: int = Query(36, ge=8, le=80),
):
    validate_scope(category, year_from, year_to)
    return kg.research_map(q, focus, category, year_from, year_to, min_papers, limit)


@router.get("/node")
def inspect_node(
    id: str = Query(..., max_length=350),
    q: str = Query("", max_length=200),
    year_from: Year = None,
    year_to: Year = None,
    paper_offset: int = Query(0, ge=0),
):
    validate_scope("", year_from, year_to)
    if not kg.KNOWLEDGE_DB_PATH.exists():
        raise HTTPException(404, "Refresh the map to index the library first.")
    try:
        return kg.inspect_node(
            id, q=q, year_from=year_from, year_to=year_to, paper_offset=paper_offset
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/build", status_code=202)
def build():
    if not kg.DB_PATH.exists():
        raise HTTPException(409, "Add papers to the library before refreshing the map.")
    return start_job("index", {})


class ExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] | None = Field(None, max_length=2000)
    topic_id: str | None = Field(None, max_length=100)
    max_chunks: int = Field(12, ge=1, le=60)


@router.post("/extract", status_code=202)
def extract(body: ExtractionInput):
    if not kg.KNOWLEDGE_DB_PATH.exists():
        raise HTTPException(409, "Refresh the map before extracting findings.")
    if body.topic_id and body.topic_id not in kg.TOPIC_BY_ID:
        raise HTTPException(422, "Unknown topic.")
    return start_job("findings", body.model_dump())


@router.post("/cancel")
def cancel():
    state = job_state()
    if state["running"] and state["kind"] == "findings":
        _cancel.set()
        update(
            message="Stopping after the current passage; saved findings will remain."
        )
    return {"job": job_state()}


@router.get("/export")
def export(
    format: Literal["json", "csv"] = "json",
    q: str = Query("", max_length=200),
    year_from: Year = None,
    year_to: Year = None,
):
    validate_scope("", year_from, year_to)
    if not kg.KNOWLEDGE_DB_PATH.exists():
        raise HTTPException(404, "Refresh the map first.")
    with closing(kg.connect()) as conn:
        papers, memberships = kg._scope(conn, q, year_from, year_to)
        fields = (
            "paper_id",
            "citation_key",
            "title",
            "source",
            "relation",
            "target",
            "conditions",
            "quote",
            "section_name",
            "page_start",
            "page_end",
            "chunk_id",
            "model",
        )
        claims = [
            {key: row[key] for key in fields}
            for row in conn.execute(
                "SELECT c.*,p.citation_key,p.title FROM kg_claims c JOIN kg_papers p USING(paper_id) ORDER BY paper_id,claim_id"
            )
            if row["paper_id"] in papers
        ]
    headers = {
        "Content-Disposition": 'attachment; filename="research-evidence.'
        + format
        + '"',
        "Cache-Control": "private, no-store",
    }
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        # Prevent spreadsheet formula execution in exported user/source text.
        writer.writerows(
            {
                key: (
                    "'" + value
                    if isinstance(value, str)
                    and value.lstrip().startswith(("=", "+", "-", "@"))
                    else value
                )
                for key, value in row.items()
            }
            for row in claims
        )
        return Response(output.getvalue(), media_type="text/csv", headers=headers)
    data = {
        "meaning": "Topics are explicit mentions. Findings are model interpretations with verified source quotes; compare conditions before drawing conclusions.",
        "papers": [
            {key: value for key, value in paper.items() if key not in {"fingerprint"}}
            for paper in papers.values()
        ],
        "topics": [
            {**kg.TOPIC_BY_ID[tid], "paper_ids": sorted(values)}
            for tid, values in memberships.items()
        ],
        "claims": claims,
    }
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers=headers,
    )
