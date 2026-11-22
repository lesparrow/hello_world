"""Serveur de modèles factice, pour les tests uniquement.

Il imite les protocoles d'Ollama (/api/tags, /api/chat) et des serveurs compatibles
OpenAI (/v1/models, /v1/chat/completions, réponse en flux SSE). La réponse est fixée par
le test : il ne s'agit pas d'un modèle de langage. Le véritable essai avec un modèle
réel est fait par tests/test_ai_live.py, dans le CI.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


class FakeModelServer:
    def __init__(self, reply: str | Callable[[list[dict]], str] = "Réponse.", models=("modele-test:1b",),
                 delay: float = 0.0, chunk: int = 12):
        self.reply, self.models, self.delay, self.chunk = reply, list(models), delay, chunk
        self.requests: list[dict] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a) -> None:
                pass

            def _json(self, code: int, data) -> None:
                body = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _pull(self, model) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                if model == "inexistant:1b":
                    self._chunk(json.dumps({"error": "pull model manifest: file does not exist"}) + "\n")
                else:
                    self._chunk(json.dumps({"status": "pulling manifest"}) + "\n")
                    for done in (0, 500_000_000, 1_000_000_000):
                        time.sleep(server.delay)
                        self._chunk(json.dumps({"status": "pulling abc", "total": 1_000_000_000,
                                                "completed": done}) + "\n")
                    self._chunk(json.dumps({"status": "success"}) + "\n")
                    server.models.append(model)
                self.wfile.write(b"0\r\n\r\n")

            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/api/tags":
                    self._json(200, {"models": [{"name": m, "size": 1_000_000_000,
                                                 "details": {"parameter_size": "1B", "quantization_level": "Q4_K_M"}}
                                                for m in server.models]})
                elif self.path == "/v1/models":
                    self._json(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in server.models]})
                else:
                    self._json(404, {"error": "not found"})

            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server.requests.append({"path": self.path, "body": body})
                if self.path == "/api/pull":
                    self._pull(body.get("model"))
                    return
                if body.get("model") not in server.models:
                    self._json(404, {"error": f"model '{body.get('model')}' not found"})
                    return
                text = server.reply(body["messages"]) if callable(server.reply) else server.reply
                pieces = [text[i:i + server.chunk] for i in range(0, len(text), server.chunk)]
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson" if self.path == "/api/chat"
                                 else "text/event-stream")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                try:
                    for p in pieces:
                        time.sleep(server.delay)
                        if self.path == "/api/chat":
                            line = json.dumps({"model": body["model"], "message": {"role": "assistant", "content": p},
                                               "done": False})
                        else:
                            line = "data: " + json.dumps({"model": body["model"], "choices": [
                                {"index": 0, "delta": {"content": p}, "finish_reason": None}]}) + "\n"
                        self._chunk(line + "\n")
                    if self.path == "/api/chat":
                        self._chunk(json.dumps({"model": body["model"], "message": {"role": "assistant", "content": ""},
                                                "done": True, "done_reason": "stop", "eval_count": len(pieces)}) + "\n")
                    else:
                        self._chunk("data: " + json.dumps({"choices": [{"index": 0, "delta": {},
                                                                         "finish_reason": "stop"}]}) + "\n\n")
                        self._chunk("data: [DONE]\n\n")
                    self.wfile.write(b"0\r\n\r\n")
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def _chunk(self, s: str) -> None:
                data = s.encode()
                self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
                self.wfile.flush()

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
