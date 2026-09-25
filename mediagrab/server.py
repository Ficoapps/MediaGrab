from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from .config import AppConfig
from .downloader import download_url

LogFn = Callable[[str], None]


class LocalServer:
    def __init__(self, config: AppConfig, log: LogFn):
        self.config = config
        self.log = log
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._server is not None

    def start(self) -> None:
        if self.running:
            return

        config = self.config
        log = self.log

        class Handler(BaseHTTPRequestHandler):
            def _cors(self) -> None:
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")

            def do_OPTIONS(self):  # noqa: N802
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self):  # noqa: N802
                if self.path == "/health":
                    body = json.dumps({"ok": True, "app": "MediaGrab"}).encode()
                    self.send_response(200)
                    self._cors()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self._cors()
                self.end_headers()

            def do_POST(self):  # noqa: N802
                if self.path != "/download":
                    self.send_response(404)
                    self._cors()
                    self.end_headers()
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    url = str(payload.get("url", "")).strip()
                    mode = str(payload.get("mode") or config.mode)
                    if mode not in {"video", "images", "all"}:
                        mode = config.mode
                    if not url:
                        raise ValueError("URL mancante")

                    threading.Thread(
                        target=self._worker,
                        args=(url, mode),
                        daemon=True,
                    ).start()
                    body = json.dumps({"ok": True, "queued": True, "mode": mode}).encode()
                    self.send_response(202)
                except Exception as exc:
                    body = json.dumps({"ok": False, "error": str(exc)}).encode()
                    self.send_response(400)

                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _worker(self, url: str, mode: str) -> None:
                try:
                    log(f"Richiesta dal browser: {url}")
                    download_url(url, config.output_dir, mode, log)
                    log("Richiesta browser completata.")
                except Exception as exc:
                    log(f"Errore richiesta browser: {exc}")

            def log_message(self, format: str, *args) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", config.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.log(f"Connettore browser attivo su http://127.0.0.1:{config.port}")

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            self.log("Connettore browser arrestato.")
