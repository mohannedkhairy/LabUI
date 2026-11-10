"""Durable reports and scheduling, with a SQLite lease shared by app workers."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import threading
import unicodedata
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from .sources import (
    SOURCES,
    Paper,
    SourceClient,
    normalize_doi,
    plain,
    safe_url,
    source_date,
)

log = logging.getLogger(__name__)
INTERVAL = timedelta(days=7)
RETRY = timedelta(hours=1)
LEASE = timedelta(minutes=30)
DDL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY CHECK(id=1), next_run TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scout_run (
    id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, heartbeat TEXT NOT NULL,
    finished_at TEXT, status TEXT NOT NULL, sources_json TEXT NOT NULL DEFAULT '{}',
    new_count INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '',
    window_start TEXT, window_end TEXT
);
CREATE TABLE IF NOT EXISTS source_checkpoint (
    source TEXT PRIMARY KEY, checked_through TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS publication (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, authors_json TEXT NOT NULL,
    abstract TEXT NOT NULL, journal TEXT NOT NULL, published TEXT NOT NULL,
    doi TEXT NOT NULL, url TEXT NOT NULL, kind TEXT NOT NULL,
    first_seen TEXT NOT NULL, sources_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS identity (
    key TEXT PRIMARY KEY, publication_id INTEGER NOT NULL REFERENCES publication(id)
);
CREATE TABLE IF NOT EXISTS report_entry (
    run_id INTEGER NOT NULL REFERENCES scout_run(id),
    publication_id INTEGER NOT NULL REFERENCES publication(id),
    PRIMARY KEY(run_id, publication_id)
);
CREATE INDEX IF NOT EXISTS publication_seen ON publication(first_seen DESC);
"""


def utcnow():
    return datetime.now(UTC)


def fingerprint(value):
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(character for character in value if character.isalnum())


def publication_week(now):
    """Seven complete UTC dates immediately before this scan's date."""
    today = now.astimezone(UTC).date()
    return today - timedelta(days=7), today - timedelta(days=1)


def in_publication_window(published, since, until):
    """Accept only an exact source publication day inside both boundaries."""
    published = source_date(published)
    return len(published) == 10 and since.isoformat() <= published <= until.isoformat()


class Scout:
    def __init__(self, path: Path, *, clock=utcnow, client_factory=None):
        self.path = Path(path)
        self.clock = clock
        self.client_factory = client_factory or (lambda: httpx.Client(
            timeout=20, follow_redirects=True,
            headers={"User-Agent": "LabUI-PublicationScout/1.0 (weekly nanobubble literature discovery)"},
        ))
        self.enabled = os.environ.get("LABUI_SCOUT_ENABLED", "1").lower() not in {"0", "false", "no"}
        self._stop = threading.Event()
        self._scheduler = None
        self._worker = None
        self._worker_run_id = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(DDL)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(scout_run)")}
            for name in ("window_start", "window_end"):
                if name not in columns:
                    conn.execute(f"ALTER TABLE scout_run ADD COLUMN {name} TEXT")
            conn.execute("INSERT OR IGNORE INTO schedule VALUES(1,?)", (self.clock().isoformat(),))

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _claim(self, due=False):
        now = self.clock()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute("SELECT * FROM scout_run WHERE status='running' ORDER BY id DESC LIMIT 1").fetchone()
            if active:
                if datetime.fromisoformat(active["heartbeat"]) + LEASE > now:
                    return None
                conn.execute("""UPDATE scout_run SET status='interrupted', finished_at=?, error=?,
                    new_count=(SELECT COUNT(*) FROM report_entry WHERE run_id=scout_run.id) WHERE id=?""",
                             (now.isoformat(), "The previous scan stopped before completion; its sources will be retried.", active["id"]))
                conn.execute("UPDATE schedule SET next_run=? WHERE id=1", (now.isoformat(),))
            next_run = conn.execute("SELECT next_run FROM schedule WHERE id=1").fetchone()[0]
            if due and datetime.fromisoformat(next_run) > now:
                return None
            since, until = publication_week(now)
            return conn.execute("""INSERT INTO scout_run(started_at,heartbeat,status,window_start,window_end)
                                VALUES(?,?,'running',?,?)""",
                                (now.isoformat(), now.isoformat(), since.isoformat(), until.isoformat())).lastrowid

    def _heartbeat(self, run_id):
        if self._stop.is_set():
            raise RuntimeError("LabUI is stopping; the scan will resume at the next startup")
        with self.connection() as conn:
            changed = conn.execute("UPDATE scout_run SET heartbeat=? WHERE id=? AND status='running'",
                                   (self.clock().isoformat(), run_id)).rowcount
            if not changed:
                raise RuntimeError("This scan's lease has expired")

    def _save(self, conn, run_id, paper: Paper):
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        if not conn.execute("SELECT 1 FROM scout_run WHERE id=? AND status='running'", (run_id,)).fetchone():
            raise RuntimeError("This scan's lease has expired")
        if not paper.relevant() or not paper.source_id:
            return False
        paper.title, paper.abstract = plain(paper.title), plain(paper.abstract)
        paper.authors = [plain(a) for a in paper.authors if plain(a)]
        paper.journal, paper.published = plain(paper.journal), source_date(paper.published)
        paper.doi, paper.url = normalize_doi(paper.doi), safe_url(paper.url)
        keys = [f"source:{paper.source}:{paper.source_id}"]
        if paper.doi:
            keys.insert(0, "doi:" + paper.doi)
        # A published article and its preprint remain distinct versions. Only
        # exact normalized titles + author bylines can join DOI-less records.
        if paper.authors:
            raw = fingerprint(paper.title) + "|" + fingerprint(paper.authors[0])
            raw += "|" + ("preprint" if paper.kind == "preprint" else "published")
            keys.append("title:" + hashlib.sha256(raw.encode()).hexdigest())
        saved = None
        for key in keys:
            candidate = conn.execute("SELECT p.* FROM identity i JOIN publication p ON p.id=i.publication_id WHERE i.key=?", (key,)).fetchone()
            if candidate and not (paper.doi and candidate["doi"] and paper.doi != candidate["doi"]):
                saved = candidate
                break
        provenance = {paper.source: {"id": paper.source_id, "url": paper.url}}
        if saved:
            sources = json.loads(saved["sources_json"])
            sources.update(provenance)
            conn.execute("""UPDATE publication SET abstract=?, authors_json=?, journal=?,
                         published=?, doi=?, url=?, sources_json=? WHERE id=?""", (
                paper.abstract if len(paper.abstract) > len(saved["abstract"]) else saved["abstract"],
                json.dumps(paper.authors) if len(paper.authors) > len(json.loads(saved["authors_json"])) else saved["authors_json"],
                saved["journal"] or paper.journal, saved["published"] or paper.published,
                saved["doi"] or paper.doi, saved["url"] or paper.url, json.dumps(sources), saved["id"],
            ))
            publication_id = saved["id"]
        else:
            publication_id = conn.execute("""INSERT INTO publication
                (title,authors_json,abstract,journal,published,doi,url,kind,first_seen,sources_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (
                paper.title, json.dumps(paper.authors), paper.abstract, paper.journal,
                paper.published, paper.doi, paper.url, paper.kind,
                self.clock().isoformat(), json.dumps(provenance),
            )).lastrowid
            conn.execute("INSERT INTO report_entry VALUES(?,?)", (run_id, publication_id))
        for key in keys:
            conn.execute("INSERT OR IGNORE INTO identity VALUES(?,?)", (key, publication_id))
        return saved is None

    def _work(self, run_id):
        outcomes = {}
        error = ""
        with self.connection() as conn:
            started = datetime.fromisoformat(conn.execute("SELECT started_at FROM scout_run WHERE id=?", (run_id,)).fetchone()[0])
        since, until = publication_week(started)
        try:
            with self.client_factory() as http:
                client = SourceClient(http, heartbeat=lambda: self._heartbeat(run_id))
                for name, method in SOURCES.items():
                    count = added = rejected = 0
                    # Publication dates, not indexing/checkpoint dates, define
                    # every scan, retry, manual run, and startup catch-up.
                    outcome = {"status": "running", "checked": 0, "added": 0,
                               "since": since.isoformat(), "through": until.isoformat(),
                               "rejected_dates": 0, "error": ""}
                    outcomes[name] = outcome
                    self._progress(run_id, outcomes)
                    try:
                        for paper in getattr(client, method)(since, until):
                            count += 1
                            if not in_publication_window(paper.published, since, until):
                                rejected += 1
                                continue
                            with self.connection() as conn:
                                added += int(self._save(conn, run_id, paper))
                        outcome.update(status="done")
                        self._heartbeat(run_id)
                        with self.connection() as conn:
                            conn.execute("""INSERT INTO source_checkpoint VALUES(?,?)
                                ON CONFLICT(source) DO UPDATE SET checked_through=excluded.checked_through""",
                                         (name, started.isoformat()))
                    except Exception as exc:  # noqa: BLE001 - one broken source must not discard the other sources
                        log.warning("Publication scout: %s failed: %s", name, exc)
                        outcome.update(status="error", error=str(exc)[:500])
                    outcome.update(checked=count, added=added, rejected_dates=rejected)
                    self._progress(run_id, outcomes)
        except Exception as exc:
            log.exception("Publication scout failed")
            error = str(exc)[:500]
        finally:
            finished = self.clock()
            successful = sum(o["status"] == "done" for o in outcomes.values())
            complete = successful == len(SOURCES) and not error
            status = "done" if complete else "partial" if successful else "error"
            with self.connection() as conn:
                changed = conn.execute("""UPDATE scout_run SET status=?,finished_at=?,sources_json=?,error=?,
                    new_count=(SELECT COUNT(*) FROM report_entry WHERE run_id=?)
                    WHERE id=? AND status='running'""",
                             (status, finished.isoformat(), json.dumps(outcomes), error, run_id, run_id)).rowcount
                if changed:
                    conn.execute("UPDATE schedule SET next_run=? WHERE id=1",
                                 ((finished + (INTERVAL if complete else RETRY)).isoformat(),))

    def _progress(self, run_id, outcomes):
        self._heartbeat(run_id)
        with self.connection() as conn:
            conn.execute("""UPDATE scout_run SET sources_json=?,
                new_count=(SELECT COUNT(*) FROM report_entry WHERE run_id=?) WHERE id=? AND status='running'""",
                         (json.dumps(outcomes), run_id, run_id))

    def run_once(self, *, due=False):
        """Synchronous entrypoint for maintenance and tests; same lease as UI."""
        run_id = self._claim(due)
        if run_id is not None:
            self._work(run_id)
        return run_id

    def trigger(self, *, due=False):
        run_id = self._claim(due)
        if run_id is None:
            return None
        self._worker_run_id = run_id
        self._worker = threading.Thread(target=self._work, args=(run_id,), daemon=True, name="publication-scout")
        self._worker.start()
        return run_id

    def start(self):
        if not self.enabled or self._scheduler and self._scheduler.is_alive():
            return
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self.trigger(due=True)
                except Exception:
                    log.exception("Could not start scheduled publication scan")
                self._stop.wait(60)

        self._scheduler = threading.Thread(target=loop, daemon=True, name="scout-scheduler")
        self._scheduler.start()

    def stop(self):
        self._stop.set()
        if self._scheduler:
            self._scheduler.join(timeout=2)
        if self._worker_run_id is not None:
            with self.connection() as conn:
                changed = conn.execute("""UPDATE scout_run SET status='interrupted',finished_at=?,error=?,
                    new_count=(SELECT COUNT(*) FROM report_entry WHERE run_id=scout_run.id)
                    WHERE id=? AND status='running'""", (
                    self.clock().isoformat(), "LabUI stopped during this scan; it will retry at the next startup.",
                    self._worker_run_id,
                )).rowcount
                if changed:
                    conn.execute("UPDATE schedule SET next_run=? WHERE id=1", (self.clock().isoformat(),))
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=1)

    @staticmethod
    def _report(row):
        if not row:
            return None
        value = dict(row)
        value["sources"] = json.loads(value.pop("sources_json"))
        return value

    def status(self):
        since, until = publication_week(self.clock())
        with self.connection() as conn:
            latest = self._report(conn.execute("SELECT * FROM scout_run ORDER BY id DESC LIMIT 1").fetchone())
            total = conn.execute("""SELECT COUNT(*) FROM publication
                WHERE length(published)=10 AND published BETWEEN ? AND ?""",
                                 (since.isoformat(), until.isoformat())).fetchone()[0]
            next_run = conn.execute("SELECT next_run FROM schedule WHERE id=1").fetchone()[0]
        running = bool(latest and latest["status"] == "running" and
                       datetime.fromisoformat(latest["heartbeat"]) + LEASE > self.clock())
        return {"running": running, "scheduled": self.enabled, "next_run": next_run if self.enabled else None,
                "latest": latest, "total": total, "sources": list(SOURCES), "interval_days": 7,
                "window_start": since.isoformat(), "window_end": until.isoformat(),
                "date_policy": "exact_publication_day", "window_timezone": "UTC"}

    def reports(self, limit=30):
        with self.connection() as conn:
            return [self._report(row) for row in conn.execute("SELECT * FROM scout_run ORDER BY id DESC LIMIT ?", (limit,))]

    def report(self, run_id):
        with self.connection() as conn:
            return self._report(conn.execute("SELECT * FROM scout_run WHERE id=?", (run_id,)).fetchone())

    def papers(self, *, run_id=None, limit=50, offset=0):
        with self.connection() as conn:
            clause, params = "", []
            if run_id is not None:
                clause = "WHERE p.id IN (SELECT publication_id FROM report_entry WHERE run_id=?)"
                params.append(run_id)
            else:
                since, until = publication_week(self.clock())
                clause = "WHERE length(p.published)=10 AND p.published BETWEEN ? AND ?"
                params.extend([since.isoformat(), until.isoformat()])
            total = conn.execute(f"SELECT COUNT(*) FROM publication p {clause}", params).fetchone()[0]
            rows = conn.execute(f"SELECT p.* FROM publication p {clause} ORDER BY p.first_seen DESC,p.id DESC LIMIT ? OFFSET ?",
                                params + [limit, offset]).fetchall()
        papers = []
        for row in rows:
            paper = dict(row)
            paper["authors"] = json.loads(paper.pop("authors_json"))
            paper["sources"] = json.loads(paper.pop("sources_json"))
            papers.append(paper)
        return {"items": papers, "total": total, "offset": offset, "limit": limit}
