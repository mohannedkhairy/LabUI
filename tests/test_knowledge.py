"""Research connections must have source evidence and respect library scopes."""

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Local_Rag" / "rag"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from ingest import extract_findings as extraction
from jfr.web import knowledge_routes as routes
from retrieval import knowledge as kg

POSITIVE = "At pH 7, NaCl concentration increases the measured nanobubble lifetime from 40 to 60 minutes under these experimental conditions."
NEGATIVE = "At pH 7, sodium chloride concentration decreases the measured nanobubble lifetime from 40 to 12 minutes under these experimental conditions."
NO_EFFECT = "At pH 7, NaCl concentration did not produce a statistically significant change in nanobubble lifetime under these experimental conditions."


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "rag.db"
        self.derived = self.root / "knowledge.db"
        self.conn = sqlite3.connect(self.source)
        self.addCleanup(self.conn.close)
        self.conn.executescript("""
        CREATE TABLE papers(paper_id TEXT PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,doi TEXT,abstract TEXT);
        CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY,paper_id TEXT,text TEXT,section_name TEXT,page_start INTEGER,page_end INTEGER,position INTEGER);
        CREATE TABLE citation_catalog(paper_id TEXT,citation_key TEXT);
        """)
        for target, value in [
            ("DB_PATH", self.source),
            ("KNOWLEDGE_DB_PATH", self.derived),
        ]:
            p = patch.object(kg, target, value)
            p.start()
            self.addCleanup(p.stop)
        app = FastAPI()
        app.include_router(routes.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        routes.update(running=False, kind=None, done=0, total=0, message="", error=None)

    def paper(
        self,
        pid="one",
        text=POSITIVE,
        title="CO₂ nanobubbles characterized with NTA",
        year=2025,
        section="Results",
        abstract="",
    ):
        self.conn.execute(
            "INSERT INTO papers VALUES(?,?,?,?,?,?)",
            (pid, title, "Cai, A.", year, "10.1/" + pid, abstract),
        )
        self.conn.execute(
            "INSERT INTO chunks VALUES(?,?,?,?,?,?,?)",
            (pid + "-chunk", pid, text, section, 3, 4, 0),
        )
        self.conn.execute(
            "INSERT INTO citation_catalog VALUES(?,?)", (pid, "cai" + str(year) + pid)
        )
        self.conn.commit()

    @staticmethod
    def claim(
        text=POSITIVE, source="NaCl concentration", relation="increases", **values
    ):
        return {
            "source": source,
            "target": "nanobubble lifetime",
            "relation": relation,
            "quote": text,
            "conditions": "At pH 7",
            **values,
        }

    def extract(self, answer=None, **options):
        answer = {"claims": [self.claim()]} if answer is None else answer
        with patch.object(extraction, "call_model", return_value=answer):
            return extraction.extract_findings("local-model", "http://local", **options)


class ResearchIndexTests(Fixture):
    def test_unrelated_database_bookkeeping_does_not_mark_the_graph_stale(self):
        self.paper()
        kg.build_index()
        self.conn.execute("CREATE TABLE unrelated_settings(key TEXT,value TEXT)")
        self.conn.execute(
            "INSERT INTO unrelated_settings VALUES('setting','new value')"
        )
        self.conn.commit()
        self.assertFalse(kg.status()["needs_refresh"])

    def test_simplified_view_keeps_weak_bridges_and_never_invents_edges(self):
        edges = [
            {
                "id": str(index),
                "source": "t" + str(index),
                "target": "p1",
                "weight": 10 - index,
            }
            for index in range(8)
        ]
        edges += [{"id": "other", "source": "t7", "target": "p2", "weight": 9}]
        simplified = kg._readable_edges(edges)
        self.assertEqual({e["id"] for e in simplified}, {e["id"] for e in edges})
        # All eight topics stay attached, including the low-weight t7 bridge.
        self.assertIn("7", {e["id"] for e in simplified})
        self.assertEqual({e["target"] for e in simplified}, {"p1", "p2"})

    def test_aliases_boundaries_and_hyphens(self):
        self.assertIn("carbon-dioxide", kg.topic_matches("CO₂ / CO2 / carbon dioxide"))
        self.assertIn("nta", kg.topic_matches("nanoparticle-tracking analysis"))
        self.assertIn("nta", kg.topic_matches("NTA"))
        self.assertIn("nacl", kg.topic_matches("sodium chloride"))
        self.assertNotIn("nacl", kg.topic_matches("NaClO4"))
        self.assertNotIn("nta", kg.topic_matches("important"))

    def test_build_preserves_source_and_legacy_graph(self):
        self.paper()
        old = self.root / "graph.db"
        old.write_bytes(b"existing graph sentinel")
        before = self.source.read_bytes()
        result = kg.build_index()
        self.assertEqual(result["mapped_papers"], 1)
        self.assertGreaterEqual(result["topics"], 4)
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(old.read_bytes(), b"existing graph sentinel")
        detail = kg.inspect_node("paper:one")
        self.assertEqual(detail["node"]["name"], "@cai2025one")
        self.assertTrue(
            any("NaCl" in passage["quote"] for passage in detail["passages"])
        )

    def test_unchanged_sources_skip_and_modified_sources_invalidate_claims(self):
        self.paper()
        kg.build_index()
        self.extract()
        second = kg.build_index()
        self.assertEqual(
            (second["changed"], second["unchanged"], second["findings"]), (0, 1, 1)
        )
        self.conn.execute(
            "UPDATE chunks SET text=?", ("Replaced source: CO2 measured by NTA.",)
        )
        self.conn.commit()
        self.assertTrue(kg.status()["needs_refresh"])
        third = kg.build_index()
        self.assertEqual(
            (third["changed"], third["findings"], third["checked_chunks"]), (1, 0, 0)
        )

    def test_reference_only_mentions_do_not_create_topic_edges(self):
        self.paper(
            text="CO2 was measured with NTA using sodium chloride.",
            title="An unrelated paper",
            section="References",
        )
        self.assertEqual(kg.build_index()["mapped_papers"], 0)

    def test_metadata_mentions_are_labeled_and_keep_unknown_pages(self):
        self.paper(
            text="No recognized topics.",
            title="Carbon dioxide study",
            section="Introduction",
        )
        kg.build_index()
        passage = kg.inspect_node("topic:carbon-dioxide")["passages"][0]
        self.assertEqual(passage["section_name"], "Title / abstract")
        self.assertIsNone(passage["page_start"])
        self.assertEqual(passage["chunk_id"], "")

    def test_deleted_papers_cascade_and_full_refresh_cleans_them(self):
        self.paper()
        kg.build_index()
        self.extract()
        self.conn.execute("DELETE FROM papers")
        self.conn.execute("DELETE FROM chunks")
        self.conn.commit()
        kg.build_index()
        with closing(kg.connect()) as c:
            for table in ["kg_papers", "kg_mentions", "kg_claims", "kg_attempts"]:
                self.assertEqual(
                    c.execute("SELECT count(*) FROM " + table).fetchone()[0], 0
                )

    def test_map_has_no_isolates_and_is_bounded(self):
        for i in range(14):
            self.paper(str(i), year=2000 + i)
        kg.build_index()
        data = kg.research_map(limit=8)
        self.assertEqual(data["shown_papers"], 8)
        endpoints = {
            edge[side] for edge in data["edges"] for side in ("source", "target")
        }
        self.assertEqual({node["id"] for node in data["nodes"]}, endpoints)
        self.assertTrue(all(edge["relation"] == "mentions" for edge in data["edges"]))

    def test_search_keys_aliases_and_year_filters(self):
        self.paper("one", year=2024)
        self.paper("two", year=2025)
        kg.build_index()
        self.assertEqual(
            kg.research_map(q="carbon dioxide", year_from=2025, min_papers=1)[
                "scope_papers"
            ],
            1,
        )
        data = kg.research_map(q="@cai2024one", min_papers=1)
        self.assertEqual(data["scope_papers"], 1)
        self.assertIn("paper:one", {node["id"] for node in data["nodes"]})
        self.assertEqual(kg.research_map(q="nonexistentxyz")["nodes"], [])

    def test_focus_and_inspector_respect_year_and_query_scope(self):
        self.paper("one", year=2024)
        self.paper("two", year=2025)
        kg.build_index()
        detail = kg.inspect_node("topic:nacl", year_from=2025)
        self.assertEqual(detail["paper_ids"], ["two"])
        self.assertTrue(all(row["paper_id"] == "two" for row in detail["passages"]))
        with self.assertRaises(KeyError):
            kg.inspect_node("paper:one", year_from=2025)
        self.assertEqual(
            kg.research_map(focus="topic:nacl", min_papers=1)["scope_papers"], 2
        )

    def test_scoped_retrieval_filters_before_limit(self):
        self.paper("one")
        self.paper("two")
        kg.build_index()
        self.assertEqual(
            kg.candidate_chunks(self.conn, "NaCl", 1, ["two"]), ["two-chunk"]
        )
        self.assertEqual(kg.candidate_chunks(self.conn, "NaCl", 1, ["outside"]), [])

    def test_related_papers_explain_shared_topics(self):
        self.paper("one")
        self.paper("two")
        kg.build_index()
        related = kg.inspect_node("paper:one")["related"]
        self.assertEqual(related[0]["paper_id"], "two")
        self.assertIn("Sodium chloride / NaCl", related[0]["shared_topics"])

    def test_writer_lock_rejects_concurrent_build(self):
        self.paper()
        with (
            kg.writer_lock(),
            self.assertRaisesRegex(RuntimeError, "already being updated"),
        ):
            kg.build_index()

    def test_missing_index_is_a_read_only_empty_state(self):
        self.paper()
        data = kg.research_map()
        self.assertEqual(data["nodes"], [])
        self.assertEqual(data["stats"]["library_papers"], 1)
        self.assertFalse(self.derived.exists())


class FindingsTests(Fixture):
    def test_only_verbatim_supported_claims_are_saved_with_provenance(self):
        self.paper()
        kg.build_index()
        result = self.extract()
        self.assertEqual(result["accepted"], 1)
        saved = kg.inspect_node("paper:one")["claims"][0]
        self.assertEqual(
            (saved["quote"], saved["page_start"], saved["page_end"], saved["model"]),
            (POSITIVE, 3, 4, "local-model"),
        )
        self.assertEqual(
            saved["text_hash"], hashlib.sha256(POSITIVE.encode()).hexdigest()
        )
        with patch.object(extraction, "call_model") as model:
            second = extraction.extract_findings("local-model", "http://local")
            self.assertEqual(second["checked"], 0)
            model.assert_not_called()

    def test_fabricated_quotes_conditions_and_entities_are_rejected(self):
        for changes in [
            {"quote": POSITIVE + " Fabricated."},
            {"conditions": "At pH 2"},
            {"source": "Calcium concentration"},
            {"target": "bubble stability"},
            {"relation": "causes"},
        ]:
            with self.subTest(changes=changes):
                claims, rejected = extraction.validate_claims(
                    {"claims": [self.claim(**changes)]}, POSITIVE
                )
                self.assertEqual((claims, rejected), ([], 1))

    def test_negation_and_hypotheses_cannot_be_positive_findings(self):
        positive = self.claim(text=NO_EFFECT)
        self.assertEqual(
            extraction.validate_claims({"claims": [positive]}, NO_EFFECT)[0], []
        )
        negative = self.claim(text=NO_EFFECT, relation="no_detected_effect")
        self.assertEqual(
            len(extraction.validate_claims({"claims": [negative]}, NO_EFFECT)[0]), 1
        )
        hypothetical = POSITIVE.replace("increases", "may increase")
        self.assertEqual(
            extraction.validate_claims(
                {"claims": [self.claim(text=hypothetical)]}, hypothetical
            )[0],
            [],
        )
        self.assertEqual(
            len(
                extraction.validate_claims(
                    {
                        "claims": [
                            self.claim(
                                text=hypothetical, relation="hypothesized_effect"
                            )
                        ]
                    },
                    hypothetical,
                )[0]
            ),
            1,
        )

    def test_model_failure_is_retryable_and_does_not_mark_chunk_complete(self):
        self.paper()
        kg.build_index()
        with (
            patch.object(extraction, "call_model", side_effect=RuntimeError("offline")),
            self.assertRaisesRegex(RuntimeError, "offline"),
        ):
            extraction.extract_findings("local-model", "http://local")
        self.assertEqual(kg.status()["checked_chunks"], 0)
        self.assertEqual(self.extract()["accepted"], 1)

    def test_empty_results_checkpoint_and_cancellation_preserves_work(self):
        self.paper("one")
        self.paper("two")
        kg.build_index()
        stopped = self.extract({"claims": []}, stop=lambda: True)
        self.assertEqual(stopped["checked"], 0)
        empty = self.extract({"claims": []}, max_chunks=1)
        self.assertEqual((empty["checked"], empty["accepted"]), (1, 0))
        self.assertEqual(self.extract({"claims": []})["checked"], 1)

    def test_different_effects_compare_aliases_across_papers_not_as_certainty(self):
        self.paper("one", text=POSITIVE)
        self.paper("two", text=NEGATIVE)
        kg.build_index()
        self.extract(paper_ids=["one"])
        self.extract(
            {
                "claims": [
                    self.claim(
                        text=NEGATIVE,
                        source="sodium chloride concentration",
                        relation="decreases",
                    )
                ]
            },
            paper_ids=["two"],
        )
        comparisons = kg.research_map()["comparisons"]
        self.assertEqual(len(comparisons), 1)
        self.assertIn("compare conditions", comparisons[0]["label"])
        self.assertEqual(
            {c["relation"] for c in comparisons[0]["claims"]},
            {"increases", "decreases"},
        )
        self.assertEqual(kg.research_map(year_from=2026)["comparisons"], [])

    def test_targeted_extraction_cannot_reach_papers_outside_scope(self):
        self.paper("one")
        self.paper("two")
        kg.build_index()
        self.extract(paper_ids=["two"], topic_id="nacl")
        self.assertEqual(kg.inspect_node("paper:one")["claims"], [])
        self.assertEqual(len(kg.inspect_node("paper:two")["claims"]), 1)

    def test_source_mutation_during_model_call_does_not_publish_stale_quote(self):
        self.paper()
        kg.build_index()

        def repair(*args):
            self.conn.execute(
                "UPDATE chunks SET text='Source repaired while model was running'"
            )
            self.conn.commit()
            return {"claims": [self.claim()]}

        with patch.object(extraction, "call_model", side_effect=repair):
            result = extraction.extract_findings("local-model", "http://local")
        self.assertEqual(result["accepted"], 0)
        self.assertEqual(kg.status()["findings"], 0)

    def test_invalid_json_or_truncated_output_is_rejected(self):
        response = {
            "message": {"content": json.dumps({"claims": []})},
            "done_reason": "length",
        }
        with patch.object(extraction.requests, "post") as post:
            post.return_value.json.return_value = response
            with self.assertRaisesRegex(ValueError, "truncated"):
                extraction.call_model(POSITIVE, "model", "http://local")


class ResearchAPITests(Fixture):
    def test_large_topic_extraction_keeps_the_full_scope_across_batches(self):
        self.paper()
        kg.build_index()
        ids = ["paper" + str(index) for index in range(150)]
        with patch.object(routes._executor, "submit") as submit:
            response = self.client.post(
                "/api/rag/knowledge/extract", json={"paper_ids": ids, "max_chunks": 12}
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(submit.call_args.args[2]["paper_ids"], ids)

    def test_topic_paper_list_paginates_without_hiding_the_full_agent_scope(self):
        for index in range(23):
            self.paper(str(index), year=2000 + index)
        kg.build_index()
        first = self.client.get("/api/rag/knowledge/node?id=topic:nacl").json()
        second = self.client.get(
            "/api/rag/knowledge/node?id=topic:nacl&paper_offset=20"
        ).json()
        self.assertEqual((len(first["papers"]), len(second["papers"])), (20, 3))
        self.assertEqual(len(first["paper_ids"]), 23)
        self.assertIsNone(second["next_paper_offset"])
        self.assertFalse(
            {p["paper_id"] for p in first["papers"]}
            & {p["paper_id"] for p in second["papers"]}
        )

    def test_graph_agent_preserves_paper_scope_without_web_or_memory(self):
        from jfr.web import rag_routes as rag

        with (
            patch.object(rag, "_get_models", return_value=(None, object(), None)),
            patch.object(rag, "_embed_query", return_value=[0.0]),
            patch.object(rag, "_search", return_value=[]) as search,
            patch.object(rag, "_web_search") as web,
            patch.object(rag._mem, "search_memories") as memories,
            patch.object(rag._mem, "add_turn"),
        ):
            result = rag.api_query(
                rag.QueryBody(
                    query="Compare NaCl results",
                    agent="evidence",
                    gen_model="model",
                    session_id="existing",
                    selected_paper_ids=["one", "two"],
                    library_only=True,
                )
            )
            self.assertEqual(result.media_type, "text/event-stream")
            self.assertEqual(search.call_args.args[-1], ["one", "two"])
            web.assert_not_called()
            memories.assert_not_called()
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            rag.api_query(rag.QueryBody(query="Compare results", library_only=True))

    def test_api_map_inspector_validation_and_missing_records(self):
        self.paper()
        kg.build_index()
        self.assertEqual(
            self.client.get("/api/rag/knowledge?min_papers=1").status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/rag/knowledge/node?id=topic:nacl").json()[
                "paper_ids"
            ],
            ["one"],
        )
        for query in [
            "limit=1000",
            "year_from=2025&year_to=2020",
            "category=unknown",
            "min_papers=0",
        ]:
            self.assertEqual(
                self.client.get("/api/rag/knowledge?" + query).status_code, 422
            )
        self.assertEqual(
            self.client.get("/api/rag/knowledge/node?id=paper:absent").status_code, 404
        )

    def test_export_includes_source_quotes_and_preserves_scope(self):
        self.paper("one", year=2024)
        self.paper("two", year=2025)
        kg.build_index()
        self.extract(paper_ids=["one"])
        result = self.client.get("/api/rag/knowledge/export?year_to=2024").json()
        self.assertEqual({p["paper_id"] for p in result["papers"]}, {"one"})
        self.assertEqual(result["claims"][0]["quote"], POSITIVE)
        self.assertEqual(result["claims"][0]["citation_key"], "cai2024one")
        csv = self.client.get("/api/rag/knowledge/export?format=csv")
        self.assertIn("attachment", csv.headers["content-disposition"])
        self.assertIn(POSITIVE, csv.text)

    def test_duplicate_jobs_cannot_queue_and_no_destructive_reset_option(self):
        self.paper()
        kg.build_index()
        routes.update(running=True)
        with patch.object(routes._executor, "submit") as submit:
            response = self.client.post("/api/rag/knowledge/build")
            self.assertEqual(response.status_code, 409)
            submit.assert_not_called()
        self.assertEqual(
            self.client.post(
                "/api/rag/knowledge/extract", json={"reset": True}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/rag/knowledge/extract", json={"max_chunks": 1000}
            ).status_code,
            422,
        )

    def test_job_is_marked_running_before_submission_and_error_is_visible(self):
        self.paper()
        with patch.object(routes._executor, "submit"):
            self.assertEqual(
                self.client.post("/api/rag/knowledge/build").status_code, 202
            )
            self.assertTrue(
                self.client.get("/api/rag/knowledge/status").json()["job"]["running"]
            )
        with patch.object(kg, "build_index", side_effect=RuntimeError("Busy source")):
            routes._run("index", {})
        state = self.client.get("/api/rag/knowledge/status").json()["job"]
        self.assertFalse(state["running"])
        self.assertEqual(state["error"], "Busy source")

    def test_page_renders_without_external_graph_library(self):
        from jfr.web.templating import make_templates

        template = make_templates().get_template("research_graph.html")
        from starlette.requests import Request

        request = Request(
            {
                "type": "http",
                "path": "/research/graph",
                "query_string": b"",
                "headers": [],
            }
        )
        rendered = template.render(request=request)
        self.assertIn("/static/knowledge.js", rendered)
        self.assertNotIn("d3@", rendered)
        self.assertIn("Findings to compare", rendered)


if __name__ == "__main__":
    unittest.main()
