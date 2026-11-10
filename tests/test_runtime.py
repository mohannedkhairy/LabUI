"""Missing transitive dependencies must be visible before feature use."""
import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Local_Rag" / "rag"))
import runtime


class RuntimeTests(unittest.TestCase):
    def test_broken_docling_dependency_reports_the_real_cause(self):
        original = importlib.import_module
        def load(name):
            if name == "docling.document_converter":
                raise ImportError("No module named 'torchvision'")
            return original(name)
        with patch.object(runtime.importlib, "import_module", side_effect=load):
            result = runtime.check_feature("pdf_ingestion")
            self.assertFalse(result["ready"])
            self.assertIn("torchvision", result["issues"][0])
            with self.assertRaisesRegex(runtime.RuntimeDependencyError, "setup.sh.*torchvision"):
                runtime.require_feature("pdf_ingestion")

    def test_missing_search_dependency_is_not_success_with_empty_results(self):
        from retrieval.web_search import web_search
        import builtins
        original = builtins.__import__
        def load(name, *args, **kwargs):
            if name == "ddgs":
                raise ModuleNotFoundError("No module named 'ddgs'")
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", side_effect=load):
            with self.assertRaisesRegex(runtime.RuntimeDependencyError, "setup.sh"):
                web_search("test")

    def test_every_web_feature_is_required_and_evaluation_is_opt_in(self):
        def check(name):
            return {"ready": name != "pdf_ingestion", "issues": ["missing parser"] if name == "pdf_ingestion" else []}
        with patch.object(runtime, "check_feature", side_effect=check):
            report = runtime.runtime_report()
            self.assertFalse(report["ready"])
            self.assertNotIn("evaluation", report["features"])
            self.assertIn("evaluation", runtime.runtime_report(include_evaluation=True)["features"])

    def test_ingestion_rejects_missing_parser_before_starting_background_work(self):
        from fastapi import HTTPException
        from jfr.web import rag_routes
        with patch.object(rag_routes, "require_feature", side_effect=runtime.RuntimeDependencyError("Run ./setup.sh")), \
             patch.object(rag_routes._ingest_trigger_executor, "submit") as submit:
            with self.assertRaises(HTTPException) as error:
                rag_routes.api_ingest_run()
            self.assertEqual(error.exception.status_code, 503)
            submit.assert_not_called()

    def test_health_is_degraded_when_models_work_but_pdf_ingestion_is_missing(self):
        from jfr.web.app import app, health
        from jfr.web import app as web_app
        from unittest.mock import MagicMock
        with patch.object(app.state, "rag_ready", True, create=True), \
             patch.object(app.state, "runtime", {"ready": False, "features": {"pdf_ingestion": {"ready": False}}}, create=True), \
             patch.object(web_app, "_conn", return_value=MagicMock()):
            result = health()
        self.assertTrue(result["rag"])
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["features"]["pdf_ingestion"]["ready"])


if __name__ == "__main__":
    unittest.main()
