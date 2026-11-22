"""Passerelle HTTP réservée au développement de l'interface dans un navigateur.

Elle n'est jamais incluse dans l'application distribuée : l'application utilise
l'entrée/sortie standard. Elle écoute uniquement sur 127.0.0.1 et exige un jeton
secret transmis par le serveur de développement Vite.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from statpfe.rpc.server import Engine

MAX_BODY = 1024 * 1024


def main() -> int:
    token = os.environ.get("STATPFE_DEV_TOKEN")
    if not token:
        print("STATPFE_DEV_TOKEN doit être défini.", file=sys.stderr)
        return 2
    port = int(os.environ.get("STATPFE_DEV_PORT", "8765"))
    engine = Engine()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/rpc" or not hmac.compare_digest(
                self.headers.get("X-Statpfe-Token", ""), token
            ):
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                self.send_error(413)
                return
            body = self.rfile.read(length).decode("utf-8")
            with lock:
                response = engine.handle(body)
            payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args) -> None:
            pass

    # Serveur à un seul fil : le moteur (et SQLite) est utilisé depuis un seul fil, comme dans l'application.
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Passerelle de développement sur http://127.0.0.1:{port}/rpc", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
