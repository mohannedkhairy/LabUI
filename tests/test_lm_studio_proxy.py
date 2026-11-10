"""Verify the opt-in adapter's actual HTTP formats without a GPU dependency."""
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from tools.lm_studio_proxy import create_app


class ProxyTests(unittest.TestCase):
    def client(self, handler):
        upstream = httpx.Client(base_url="http://lm.test/v1/", transport=httpx.MockTransport(handler))
        self.addCleanup(upstream.close)
        client = TestClient(create_app("http://lm.test/v1", client=upstream))
        self.addCleanup(client.close)
        return client

    def test_tags_exclude_embedding_and_reranking_models_from_chat_picker(self):
        def handler(request):
            self.assertEqual(str(request.url), "http://lm.test/v1/models")
            return httpx.Response(200, json={"data": [{"id": "qwen/test"}, {"id": "text-embedding-nomic"},
                                                     {"id": "Qwen3-Reranker-4B"}, {"id": "qwen3-embedding-4b"}]})
        self.assertEqual(self.client(handler).get("/api/tags").json(), {"models": [{"name": "qwen/test"}]})

    def test_nonstream_chat_translates_options_and_images(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            payload = json.loads(request.content)
            self.assertEqual(payload["temperature"], 0.2)
            self.assertEqual(payload["max_tokens"], 128)
            self.assertEqual(payload["reasoning_effort"], "none")
            self.assertNotIn("num_ctx", payload)
            self.assertNotIn("options", payload)
            self.assertEqual(payload["messages"][0]["content"][1]["image_url"]["url"], "data:image/png;base64,abc")
            return httpx.Response(200, json={"choices": [{"message": {"content": "Answer"}, "finish_reason": "stop"}]})
        with patch.dict("os.environ", {}, clear=True):
            response = self.client(handler).post("/api/chat", json={
                "model": "qwen/test", "messages": [{"role": "user", "content": "Read", "images": ["abc"]}],
                "stream": False, "options": {"temperature": 0.2, "num_predict": 128, "num_ctx": 8192},
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"]["content"], "Answer")
        self.assertTrue(response.json()["done"])

    def test_stream_converts_sse_to_ollama_lines_and_ignores_reasoning(self):
        events = [
            {"choices": [{"delta": {"reasoning_content": "hidden"}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "Hello "}, "finish_reason": None}]},
            {"choices": [{"delta": {"content": "world"}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "stop"}]},
        ]
        sse = ": keepalive\n\n" + "".join("data: " + json.dumps(e) + "\n\n" for e in events) + "data: [DONE]\n\n"
        client = self.client(lambda request: httpx.Response(200, text=sse))
        response = client.post("/api/chat", json={"model": "test", "messages": []})
        lines = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual("".join(line["message"]["content"] for line in lines), "Hello world")
        self.assertTrue(lines[-1]["done"])

    def test_truncated_stream_does_not_report_success(self):
        sse = 'data: {"choices":[{"delta":{"content":"Partial"},"finish_reason":null}]}\n\n'
        client = self.client(lambda request: httpx.Response(200, text=sse))
        with self.assertRaisesRegex(ValueError, "without a complete answer"):
            client.post("/api/chat", json={"model": "test", "messages": []})

    def test_token_limit_is_an_error_for_summaries(self):
        client = self.client(lambda request: httpx.Response(200, json={
            "choices": [{"message": {"content": "Partial"}, "finish_reason": "length"}],
        }))
        response = client.post("/api/chat", json={"model": "test", "messages": [], "stream": False})
        self.assertEqual(response.status_code, 502)

    def test_memory_extraction_uses_openai_response_shape(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertFalse(payload["stream"])
            self.assertEqual(payload["messages"][0]["content"], "Extract findings")
            return httpx.Response(200, json={"choices": [{"message": {"content": "none"}}]})
        response = self.client(handler).post("/v1/chat/completions", json={
            "model": "test", "messages": [{"role": "user", "content": "Extract findings"}], "stream": False,
        })
        self.assertEqual(response.json()["choices"][0]["message"]["content"], "none")

    def test_upstream_auth_error_is_preserved_without_exposing_response(self):
        client = self.client(lambda request: httpx.Response(401, text="private server details"))
        response = client.get("/api/tags")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("private", response.text)

    def test_unreachable_server_returns_bad_gateway(self):
        def handler(request):
            raise httpx.ConnectError("Connection refused", request=request)
        self.assertEqual(self.client(handler).get("/api/tags").status_code, 502)


if __name__ == "__main__":
    unittest.main()
