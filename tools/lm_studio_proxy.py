"""Local Ollama protocol adapter for the GPU's LM Studio server.

Run with start-lm-studio.sh or the labui-model systemd user service.
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager, closing
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


def local_settings():
    directory = Path.home() / ".config" / "local-model"
    path = directory / "config.json"
    config = json.loads(path.read_text()) if path.exists() else {}
    url = os.environ.get("LM_STUDIO_URL", config.get("base_url", "http://localhost:1234/v1"))
    url = url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    token = os.environ.get("LM_STUDIO_API_KEY", "")
    if not token and (directory / "token").exists():
        token = (directory / "token").read_text().strip()
    return url, token, os.environ.get("LM_STUDIO_MODEL", config.get("model", ""))


class ChatBody(BaseModel):
    model: str = Field(min_length=1)
    messages: list[dict]
    stream: bool = True
    options: dict = Field(default_factory=dict)
    think: bool | None = None


def chat_payload(body: ChatBody) -> dict:
    messages = []
    for original in body.messages:
        message = dict(original)
        images = message.pop("images", [])
        if images:
            message["content"] = [
                {"type": "text", "text": message.get("content", "")},
                *[{"type": "image_url", "image_url": {
                    "url": image if image.startswith("data:") else f"data:image/png;base64,{image}"
                }} for image in images],
            ]
        messages.append(message)
    payload = {"model": body.model, "messages": messages, "stream": body.stream}
    for key in ("temperature", "top_p", "seed", "stop"):
        if key in body.options:
            payload[key] = body.options[key]
    payload["max_tokens"] = body.options.get("num_predict", 4096)
    # Verified against this workstation's Qwen server. Other models inherit
    # their server setting unless explicitly overridden for this test session.
    effort = os.environ.get("LM_STUDIO_REASONING_EFFORT")
    if effort or ("qwen" in body.model.lower() and body.think is not True):
        payload["reasoning_effort"] = effort or "none"
    # Ollama's num_ctx is deliberately not sent: LM Studio owns context sizing.
    return payload


def create_app(base_url: str, api_key: str = "", client: httpx.Client | None = None):
    upstream = client or httpx.Client(
        base_url=base_url.rstrip("/") + "/",
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        timeout=httpx.Timeout(300, connect=5),
        trust_env=False,
    )

    @asynccontextmanager
    async def lifespan(app):
        yield
        if client is None:
            upstream.close()

    app = FastAPI(title="LabUI LM Studio adapter", lifespan=lifespan)

    def send(path, payload=None, stream=False):
        request = upstream.build_request("GET" if payload is None else "POST", path, json=payload)
        try:
            response = upstream.send(request, stream=stream)
        except httpx.RequestError as exc:
            raise HTTPException(502, "LM Studio is unreachable") from exc
        if response.is_error:
            status = response.status_code
            response.close()
            raise HTTPException(status, f"LM Studio returned HTTP {status}")
        return response

    @app.get("/api/tags")
    def tags():
        with closing(send("models")) as response:
            return {"models": [{"name": model["id"]} for model in response.json().get("data", [])
                               if not any(kind in model["id"].lower() for kind in ('embedding', 'rerank'))]}

    @app.post("/api/chat")
    def chat(body: ChatBody):
        response = send("chat/completions", chat_payload(body), stream=body.stream)
        if not body.stream:
            with closing(response):
                result = response.json()
                choice = result["choices"][0]
                if choice.get("finish_reason") == "length":
                    raise HTTPException(502, "LM Studio output hit its token limit; increase num_predict")
                content = choice["message"].get("content") or ""
                if not content:
                    raise HTTPException(502, "LM Studio returned no answer text")
                return {"model": body.model, "message": {"role": "assistant", "content": content}, "done": True}

        def lines():
            finished = False
            has_text = False
            try:
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    item = json.loads(data)
                    if "error" in item:
                        raise ValueError("LM Studio reported a stream error")
                    for choice in item.get("choices", []):
                        content = choice.get("delta", {}).get("content") or ""
                        if content:
                            has_text = True
                            yield json.dumps({"message": {"role": "assistant", "content": content}, "done": False}) + "\n"
                        reason = choice.get("finish_reason")
                        if reason == "length":
                            raise ValueError("LM Studio output hit its token limit; increase num_predict")
                        if reason:
                            finished = True
                if not finished or not has_text:
                    raise ValueError("LM Studio stream ended without a complete answer")
                yield json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}) + "\n"
            finally:
                response.close()

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.post("/v1/chat/completions")
    def completions(payload: dict):
        # LabUI's background memory extraction uses the OpenAI-compatible path.
        if payload.get("stream"):
            raise HTTPException(400, "Use /api/chat for streamed requests")
        if "qwen" in payload.get("model", "").lower():
            payload.setdefault("reasoning_effort", os.environ.get("LM_STUDIO_REASONING_EFFORT", "none"))
        payload.setdefault("max_tokens", 4096)
        with closing(send("chat/completions", payload)) as response:
            return response.json()

    return app


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    base_url, api_key, model = local_settings()
    app = create_app(base_url, api_key)
    if args.check:
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            names = [m["name"] for m in response.json()["models"]]
            if not names or (model and model not in names):
                raise SystemExit("Configured chat model is unavailable in LM Studio")
            print(f"LM Studio ready: {base_url}; model: {model or names[0]}")
    else:
        uvicorn.run(app, host="127.0.0.1", port=args.port)
