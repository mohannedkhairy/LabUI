"""Discovery must not miss retries, invent dates, duplicate papers, or hide failures."""
import sqlite3
import tempfile
import threading
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jfr.scout.service import LEASE, Scout, in_publication_window, publication_week
from jfr.scout.sources import TOPIC, Paper, SourceClient, normalize_doi, safe_url
from jfr.web.scout_routes import router

NOW = datetime(2026, 11, 6, 15, tzinfo=UTC)


def paper(source="Crossref", source_id="10.1234/example", **changes):
    values = {"source": source, "source_id": source_id, "title": "Nanobubble stability in saline water",
              "authors": ["Alex Smith"], "doi": "10.1234/example", "published": "2026-11-03",
              "abstract": "Nanobubbles remain stable under these experimental conditions.",
              "url": "https://doi.org/10.1234/example", "journal": "Surface Science"}
    values.update(changes)
    return Paper(**values)


def crossref_item(**changes):
    values = {"DOI": "10.1234/example", "title": ["Nanobubble stability in saline water"],
              "type": "journal-article", "published-online": {"date-parts": [[2026, 11, 3]]},
              "author": [{"given": "Alex", "family": "Smith"}], "abstract": "<jats:p>Nanobubbles &amp; salt.</jats:p>"}
    values.update(changes)
    return values


class ScoutFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "scout.sqlite"
        self.now = NOW
        self.scout = Scout(self.path, clock=lambda: self.now)
        self.addCleanup(self.scout.stop)

    def sources(self, crossref=None, europe=None, arxiv=None):
        """Replace networking only; exercise real persistence and orchestration."""
        stack = []
        for name, values in [("crossref", crossref or []), ("europe_pmc", europe or []), ("arxiv", arxiv or [])]:
            patcher = patch.object(SourceClient, name, side_effect=values if isinstance(values, Exception) else None,
                                   return_value=values if not isinstance(values, Exception) else None)
            stack.append(patcher.start())
            self.addCleanup(patcher.stop)
        return stack


class ScoutPersistenceTests(ScoutFixture):
    def test_deduplicates_doi_case_prefix_and_sources_and_repeated_scans(self):
        self.sources([paper()], [paper("Europe PMC", "MED/123", doi="https://doi.org/10.1234/EXAMPLE", abstract="A longer nanobubble abstract with additional reported findings.")])
        first = self.scout.run_once()
        second = self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 1)
        self.assertEqual(self.scout.report(first)["new_count"], 1)
        self.assertEqual(self.scout.report(second)["new_count"], 0)
        saved = self.scout.papers()["items"][0]
        self.assertEqual(set(saved["sources"]), {"Crossref", "Europe PMC"})
        self.assertIn("longer", saved["abstract"])
        self.assertEqual(self.scout.papers(run_id=first)["total"], 1)
        self.assertEqual(self.scout.papers(run_id=second)["total"], 0)

    def test_doi_less_exact_title_author_dedup_and_distinct_dois(self):
        self.sources([paper(doi="")], [paper("Europe PMC", "MED/1", doi="")])
        self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 1)
        with self.scout.connection() as conn:
            run_id = self.scout._claim()
            self.scout._save(conn, run_id, paper("Crossref", "another", doi="10.1234/one"))
            self.scout._save(conn, run_id, paper("Crossref", "third", doi="10.1234/two"))
        self.assertEqual(self.scout.status()["total"], 2)

    def test_preprint_is_distinct_and_arxiv_versions_are_one_record(self):
        self.sources([paper()], arxiv=[paper("arXiv", "2611.12345", doi="", kind="preprint")])
        self.scout.run_once()
        self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 2)
        self.assertEqual({p["kind"] for p in self.scout.papers()["items"]}, {"article", "preprint"})

    def test_irrelevant_matches_and_imprecise_dates_are_excluded(self):
        self.sources([paper(title="A study of nanoparticles", abstract="No bubble research here.", source_id="irrelevant"),
                      paper(published="2026-11", abstract=""), paper(source_id="year", published="2026"),
                      paper(source_id="missing", published="")])
        self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 0)
        self.assertEqual(self.scout.status()["latest"]["sources"]["Crossref"]["rejected_dates"], 3)

    def test_schedule_survives_recreation_and_overdue_scan_runs(self):
        mocks = self.sources([paper()])
        self.scout.run_once(due=True)
        expected = self.now + timedelta(days=7)
        restarted = Scout(self.path, clock=lambda: self.now)
        self.assertEqual(restarted.status()["next_run"], expected.isoformat())
        self.assertIsNone(restarted.run_once(due=True))
        self.now += timedelta(days=10)
        self.assertIsNotNone(restarted.run_once(due=True))
        self.assertEqual(mocks[0].call_count, 2)
        self.assertEqual(mocks[0].call_args.args, publication_week(self.now))
        self.assertEqual(self.scout.papers()["total"], 0)

    def test_partial_failure_keeps_good_results_and_failed_checkpoint_retries(self):
        mocks = self.sources([paper()], RuntimeError("Source offline"))
        first = self.scout.run_once()
        self.assertEqual(self.scout.report(first)["status"], "partial")
        self.assertEqual(self.scout.report(first)["sources"]["Europe PMC"]["error"], "Source offline")
        self.assertEqual(self.scout.status()["total"], 1)
        self.assertEqual(self.scout.status()["next_run"], (NOW + timedelta(hours=1)).isoformat())
        with self.scout.connection() as conn:
            self.assertIsNone(conn.execute("SELECT * FROM source_checkpoint WHERE source='Europe PMC'").fetchone())
        mocks[1].side_effect = None
        mocks[1].return_value = [paper("Europe PMC", "MED/2", doi="10.1234/new", title="Ultrafine bubbles in water treatment")]
        self.now += timedelta(hours=1)
        self.scout.run_once(due=True)
        self.assertEqual(self.scout.status()["latest"]["status"], "done")
        self.assertEqual(self.scout.status()["total"], 2)
        self.assertEqual(mocks[1].call_args.args, publication_week(self.now))

    def test_mid_page_failure_retains_results_and_does_not_advance_source(self):
        def broken(*args):
            yield paper()
            raise RuntimeError("Page two failed")
        self.sources()
        with patch.object(SourceClient, "crossref", side_effect=broken):
            self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 1)
        self.assertEqual(self.scout.status()["latest"]["new_count"], 1)
        with self.scout.connection() as conn:
            self.assertIsNone(conn.execute("SELECT * FROM source_checkpoint WHERE source='Crossref'").fetchone())

    def test_all_sources_failing_is_error_and_successful_zero_is_done(self):
        mocks = self.sources(RuntimeError("Offline"), RuntimeError("Offline"), RuntimeError("Offline"))
        self.scout.run_once()
        self.assertEqual(self.scout.status()["latest"]["status"], "error")
        for mock in mocks:
            mock.side_effect = None
            mock.return_value = []
        self.scout.run_once()
        self.assertEqual(self.scout.status()["latest"]["status"], "done")
        self.assertEqual(self.scout.status()["latest"]["new_count"], 0)

    def test_only_one_worker_can_claim_and_stale_scan_recovers(self):
        other = Scout(self.path, clock=lambda: self.now)
        barrier = threading.Barrier(2)
        results = []
        def claim(scout):
            barrier.wait()
            results.append(scout._claim())
        threads = [threading.Thread(target=claim, args=(s,)) for s in [self.scout, other]]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(sum(r is not None for r in results), 1)
        old_id = next(r for r in results if r is not None)
        self.now += LEASE + timedelta(seconds=1)
        new_id = other._claim(due=True)
        self.assertIsNotNone(new_id)
        self.assertEqual(self.scout.report(old_id)["status"], "interrupted")
        with self.assertRaisesRegex(RuntimeError, "lease"):
            self.scout._heartbeat(old_id)

    def test_disabled_schedule_still_allows_manual_scan(self):
        self.sources()
        with patch.dict("os.environ", {"LABUI_SCOUT_ENABLED": "0"}):
            scout = Scout(self.path, clock=lambda: self.now)
        scout.start()
        self.assertFalse(scout.status()["scheduled"])
        self.assertIsNone(scout._scheduler)
        self.assertIsNotNone(scout.run_once())

    def test_shutdown_releases_own_run_for_immediate_restart(self):
        with patch.object(self.scout, "_work"):
            run_id = self.scout.trigger()
            self.scout._worker.join(timeout=5)
        self.scout.stop()
        self.assertEqual(self.scout.report(run_id)["status"], "interrupted")
        self.sources()
        restarted = Scout(self.path, clock=lambda: self.now)
        self.assertIsNotNone(restarted.run_once(due=True))

    def test_failed_sources_search_only_current_week_after_long_outage(self):
        mocks = self.sources(europe=RuntimeError("Offline"))
        self.scout.run_once()
        self.now += timedelta(days=50)
        self.scout.run_once()
        self.assertEqual(mocks[1].call_args.args, publication_week(self.now))

    def test_old_online_dates_do_not_become_new_from_future_print_issues(self):
        self.sources([paper(published="2026-01-01"),
                      paper("Europe PMC", "MED/1", published="2026-10", doi="10.1234/partial"),
                      paper(source_id="valid", doi="10.1234/valid")])
        self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 1)
        self.assertEqual(self.scout.papers()["items"][0]["published"], "2026-11-03")

    def test_week_boundaries_are_inclusive_and_today_future_old_dates_rejected(self):
        since, until = publication_week(NOW)
        self.assertEqual((since.isoformat(), until.isoformat()), ("2026-10-30", "2026-11-05"))
        for value in ["2026-10-30", "2026-11-03", "2026-11-05"]:
            self.assertTrue(in_publication_window(value, since, until), value)
        for value in ["2026-10-29", "2026-11-06", "2026-11-07", "2026-11", "2026", "", "invalid", "2026-W45-1"]:
            self.assertFalse(in_publication_window(value, since, until), value)

    def test_sources_cannot_bypass_local_week_filter_with_old_or_future_results(self):
        records = [paper(source_id="start", doi="10.1234/start", published="2026-10-30"),
                   paper(source_id="end", doi="10.1234/end", published="2026-11-05"),
                   paper(source_id="old", doi="10.1234/old", published="2026-10-29"),
                   paper(source_id="future", doi="10.1234/future", published="2027-01-01")]
        self.sources(records)
        run_id = self.scout.run_once()
        self.assertEqual({p["published"] for p in self.scout.papers()["items"]}, {"2026-10-30", "2026-11-05"})
        self.assertEqual(self.scout.report(run_id)["window_start"], "2026-10-30")
        self.assertEqual(self.scout.report(run_id)["window_end"], "2026-11-05")
        self.assertEqual(self.scout.report(run_id)["sources"]["Crossref"]["rejected_dates"], 2)

    def test_scheduler_runs_without_dashboard_visit_or_manual_trigger(self):
        self.sources([paper()])
        finished = threading.Event()
        real_work = self.scout._work
        def work(run_id):
            real_work(run_id)
            finished.set()
        with patch.object(self.scout, "_work", side_effect=work):
            self.scout.start()
            self.assertTrue(finished.wait(timeout=5), "Automatic scan never started")
        self.assertEqual(self.scout.status()["latest"]["status"], "done")
        self.assertEqual(self.scout.status()["next_run"], (NOW + timedelta(days=7)).isoformat())

    def test_existing_database_reports_survive_window_column_migration(self):
        path = self.path.with_name("legacy.sqlite")
        with sqlite3.connect(path) as conn:
            conn.execute("""CREATE TABLE scout_run (
                id INTEGER PRIMARY KEY, started_at TEXT, heartbeat TEXT, finished_at TEXT,
                status TEXT, sources_json TEXT DEFAULT '{}', new_count INTEGER DEFAULT 0,
                error TEXT DEFAULT '')""")
            conn.execute("INSERT INTO scout_run(id,started_at,heartbeat,status) VALUES(1,?,?,'done')",
                         (NOW.isoformat(), NOW.isoformat()))
        migrated = Scout(path, clock=lambda: self.now)
        self.assertIsNone(migrated.report(1)["window_start"])
        self.assertEqual(migrated.report(1)["status"], "done")
        self.sources()
        run_id = migrated.run_once()
        self.assertEqual(migrated.report(run_id)["window_start"], "2026-10-30")
        self.assertEqual(migrated.report(run_id)["window_end"], "2026-11-05")

    def test_non_latin_titles_and_authors_do_not_collapse_to_one_identity(self):
        self.sources([paper(source_id="one", title="Nanobubbles 稳定性", authors=["张三"], doi=""),
                      paper(source_id="two", title="Nanobubbles 形成", authors=["李四"], doi="")])
        self.scout.run_once()
        self.assertEqual(self.scout.status()["total"], 2)


class SourceApiTests(unittest.TestCase):
    def client(self, handler):
        http = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(http.close)
        return SourceClient(http, sleep=lambda _: None)

    def test_crossref_pagination_query_variants_and_source_dates(self):
        requests = []
        def handler(request):
            requests.append(request)
            if request.url.params["cursor"] == "*":
                return httpx.Response(200, json={"message": {"items": [crossref_item()] * 100, "next-cursor": "page2"}})
            return httpx.Response(200, json={"message": {"items": [crossref_item(DOI="10.1234/last")]}})
        papers = list(self.client(handler).crossref(date(2026, 11, 1), date(2026, 11, 6)))
        self.assertEqual(len(requests), 8)
        self.assertEqual(len(papers), 404)
        self.assertEqual(papers[0].published, "2026-11-03")
        self.assertEqual(papers[0].abstract, "Nanobubbles & salt.")
        self.assertIn("from-pub-date:2026-11-01", requests[0].url.params["filter"])
        self.assertIn("until-pub-date:2026-11-06", requests[0].url.params["filter"])
        self.assertNotIn("index-date", requests[0].url.params["filter"])
        self.assertEqual(len({r.url.params["query"] for r in requests}), 4)

    def test_crossref_online_date_wins_over_generic_year_and_future_print(self):
        client = self.client(lambda _: httpx.Response(200, json={"message": {"items": [crossref_item(
            published={"date-parts": [[2026]]}, **{"published-print": {"date-parts": [[2027, 1, 1]]}})]}}))
        result = next(client.crossref(date(2026, 11, 1), date(2026, 11, 6)))
        self.assertEqual(result.published, "2026-11-03")

    def test_page_limit_reports_incomplete_instead_of_silent_truncation(self):
        client = self.client(lambda _: httpx.Response(200, json={"message": {"items": [crossref_item()] * 100, "next-cursor": "next"}}))
        with patch("jfr.scout.sources.MAX_PAGES", 1), self.assertRaisesRegex(RuntimeError, "incomplete"):
            list(client.crossref(date(2026, 11, 1), date(2026, 11, 6)))

    def test_europe_pmc_cursor_and_preprint_normalization(self):
        requests = []
        def handler(request):
            requests.append(request)
            result = {"source": "PPR", "id": "42", "title": "Ultrafine bubbles", "firstPublicationDate": "2026-11-01",
                      "authorList": {"author": [{"fullName": "Smith A"}]}, "abstractText": "<p>Ultrafine bubbles in medicine.</p>"}
            return httpx.Response(200, json={"resultList": {"result": [result]}, "hitCount": 2, "nextCursorMark": "page2"})
        papers = list(self.client(handler).europe_pmc(date(2026, 11, 1), date(2026, 11, 6)))
        self.assertEqual(requests[1].url.params["cursorMark"], "page2")
        self.assertIn("FIRST_PDATE:[2026-11-01 TO 2026-11-06]", requests[0].url.params["query"])
        self.assertEqual(papers[0].kind, "preprint")
        self.assertEqual(papers[0].url, "https://europepmc.org/article/PPR/42")

    def test_arxiv_version_id_and_journal_doi_remain_distinct(self):
        requests = []
        xml = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:os="http://a9.com/-/spec/opensearch/1.1/" xmlns:ar="http://arxiv.org/schemas/atom">
            <os:totalResults>1</os:totalResults><entry><id>http://arxiv.org/abs/2611.12345v3</id>
            <title>Surface nanobubbles</title><summary>Nanobubble dynamics.</summary><published>2026-11-02T00:00:00Z</published>
            <ar:doi>10.1234/journal-version</ar:doi><author><name>Alex Smith</name></author></entry></feed>'''
        def handler(request):
            requests.append(request)
            return httpx.Response(200, text=xml)
        papers = list(self.client(handler).arxiv(date(2026, 11, 1), date(2026, 11, 6)))
        self.assertIn("submittedDate:[202611010000 TO 202611062359]", requests[0].url.params["search_query"])
        self.assertEqual(papers[0].source_id, "2611.12345")
        self.assertEqual(papers[0].published, "2026-11-02")
        self.assertEqual(papers[0].doi, "")
        self.assertEqual(papers[0].kind, "preprint")

    def test_rate_limit_retries_and_invalid_payloads_raise(self):
        attempts = []
        def handler(request):
            attempts.append(request)
            return httpx.Response(429 if len(attempts) < 3 else 200, json={"message": {"items": []}})
        self.assertEqual(list(self.client(handler).crossref(date(2026, 11, 1), date(2026, 11, 6))), [])
        self.assertEqual(len(attempts), 6)
        client = self.client(lambda _: httpx.Response(200, json={"message": {}}))
        with self.assertRaises(KeyError):
            list(client.crossref(date(2026, 11, 1), date(2026, 11, 6)))

    def test_topic_and_safe_links(self):
        for text in ["nanobubbles", "nano-bubbles", "nano bubbles", "ultrafine bubbles", "ultra-fine gas bubbles"]:
            self.assertRegex(text, TOPIC)
        self.assertFalse(TOPIC.search("nanoparticles"))
        self.assertEqual(normalize_doi("https://doi.org/10.1234/EXAMPLE"), "10.1234/example")
        for url in ["javascript:alert(1)", "https://user:secret@example.com", "https://[bad"]:
            self.assertEqual(safe_url(url), "")


class ScoutWebTests(ScoutFixture):
    def setUp(self):
        super().setUp()
        self.app = FastAPI()
        self.app.state.publication_scout = self.scout
        self.app.include_router(router)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def test_empty_and_populated_report_render_and_escape_source_content(self):
        self.assertEqual(self.client.get("/research/scout").status_code, 200)
        self.sources([paper(title='Nanobubbles <script>alert("x")</script>', abstract="<b>Source abstract</b>")])
        run_id = self.scout.run_once()
        for url in ["/research/scout", f"/research/scout?run_id={run_id}", "/research/scout/widget"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Nanobubbles", response.text)
            self.assertNotIn('<script>alert("x")</script>', response.text)
        self.assertIn("Source abstract", self.client.get("/research/scout").text)
        self.assertEqual(self.client.get("/research/scout?run_id=999").status_code, 404)

    def test_manual_trigger_queues_and_duplicate_click_does_not_queue_twice(self):
        with patch.object(self.scout, "_work") as work:
            response = self.client.post("/api/scout/run")
            self.assertEqual(response.status_code, 202)
            self.scout._worker.join(timeout=5)
            self.assertEqual(work.call_count, 1)
            self.assertEqual(self.client.post("/api/scout/run").json()["started"], False)

    def test_dashboard_and_default_results_hide_past_weeks_without_deleting_reports(self):
        self.sources([paper()])
        run_id = self.scout.run_once()
        self.now += timedelta(days=8)
        for url in ["/research/scout", "/research/scout/widget"]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("Nanobubble stability in saline water", response.text)
            self.assertIn("2026-11-07", response.text)
            self.assertIn("2026-11-13", response.text)
        self.assertEqual(self.client.get("/api/scout/papers").json()["total"], 0)
        self.assertIn("Nanobubble stability in saline water", self.client.get(f"/research/scout?run_id={run_id}").text)

    def test_api_pagination_validation_and_source_failure_visible(self):
        self.sources([paper()], RuntimeError("Source offline"))
        self.scout.run_once()
        self.assertEqual(self.client.get("/api/scout/papers?limit=1").json()["total"], 1)
        self.assertEqual(self.client.get("/api/scout/papers?offset=1").json()["items"], [])
        self.assertEqual(self.client.get("/api/scout/papers?offset=-1").status_code, 422)
        self.assertEqual(self.client.get("/api/scout/reports").json()["items"][0]["status"], "partial")
        self.assertIn("Incomplete coverage", self.client.get("/research/scout/widget").text)
        self.assertIn("Source offline", self.client.get("/research/scout/widget").text)


if __name__ == "__main__":
    unittest.main()
