"""Tiny OpenAI-compatible mock service for Docker-based integration tests."""

import hashlib
import json
import math
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

EMBEDDING_DIM = 8
MODEL = "mock-model"


def _embedding(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [((byte / 255.0) * 2.0 - 1.0) for byte in digest[:EMBEDDING_DIM]]
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def _content(prompt: str) -> str:
    if "tldr" in prompt and "contributions" in prompt:
        return json.dumps(
            {
                "tldr": "Docker mock 速读卡",
                "contributions": ["提出模拟方法 [Section: Method | Chunk: 0]"],
                "method": "模拟方法 [Section: Method | Chunk: 0]",
                "experiments": "模拟实验 [Section: Experiments | Chunk: 1]",
                "limitations": "未提及",
                "takeaways": ["先读方法"],
                "sections": [
                    {"title": "Method", "summary": "模拟方法摘要", "chunk_indexes": [0]}
                ],
            },
            ensure_ascii=False,
        )
    if "对比助手" in prompt:
        return json.dumps(
            {
                "method": "模拟方法 [Section: Method | Chunk: 0]",
                "datasets": "未提及",
                "metrics": "模拟指标",
                "limitations": "未提及",
            },
            ensure_ascii=False,
        )
    if "翻译成中文" in prompt:
        return "这是 Docker mock 翻译。"
    if "简单的中文重述" in prompt:
        return "这是 Docker mock 简化解释。"
    return "这是 Docker mock LLM 的回答。 [Section: Method | Chunk: 0]"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/v1/embeddings":
            self._embeddings(payload)
            return
        if self.path == "/v1/chat/completions":
            self._chat(payload)
            return
        self._json(404, {"error": "not found"})

    def _embeddings(self, payload: dict) -> None:
        raw = payload.get("input", "")
        texts = [raw] if isinstance(raw, str) else [str(item) for item in raw]
        self._json(
            200,
            {
                "object": "list",
                "model": payload.get("model", "mock-embed"),
                "data": [
                    {"object": "embedding", "index": index, "embedding": _embedding(text)}
                    for index, text in enumerate(texts)
                ],
                "usage": {"prompt_tokens": len(texts), "total_tokens": len(texts)},
            },
        )

    def _chat(self, payload: dict) -> None:
        messages = payload.get("messages") or []
        prompt = "\n".join(str(item.get("content", "")) for item in messages)
        content = _content(prompt)
        if payload.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            parts = [content[: len(content) // 2], content[len(content) // 2 :]]
            for part in parts:
                chunk = {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": MODEL,
                    "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
            done = {
                "id": "chatcmpl-mock",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": MODEL,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": len(content), "total_tokens": 10 + len(content)},
            }
            self.wfile.write(f"data: {json.dumps(done, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())
            self.wfile.flush()
            return
        self._json(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": MODEL,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": len(content), "total_tokens": 10 + len(content)},
            },
        )

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
