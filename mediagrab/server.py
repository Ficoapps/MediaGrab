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
            def _common_headers(self) -> None:
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                origin = self.headers.get("Origin", "")
                if origin.startswith(("chrome-extension://", "edge-extension://", "moz-extension://")):
                    self.send_header("Access-Control-Allow-Origin", origin)

            def do_OPTIONS(self):  # noqa: N802
                self.send_response(204)
                self._common_headers()
                self.end_headers()

            def do_GET(self):  # noqa: N802
                if self.path == "/health":
                    body = json.dumps({"ok": True, "app": "MediaGrab", "version": "0.2.0"}).encode()
                    self.send_response(200)
                    self._common_headers()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self._common_headers()
                self.end_headers()

            def do_POST(self):  # noqa: N802
                if self.path != "/download":
                    self.send_response(404)
                    self._common_headers()
                    self.end_headers()
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length > 512_000:
                        raise ValueError("Richiesta troppo grande")
                    payload = json.loads(self.rfile.read(length) or b"{}")
                    url = str(payload.get("url", "")).strip()
                    mode = str(payload.get("mode") or config.mode)
                    if mode not in {"video", "images", "all"}:
                        mode = config.mode
                    if not url.startswith(("http://", "https://")):
                        raise ValueError("URL mancante o non valido")

                    raw_candidates = payload.get("candidates") or []
                    if not isinstance(raw_candidates, list):
                        raw_candidates = []
                    candidates = [
                        str(item).strip()
                        for item in raw_candidates[:300]
                        if isinstance(item, str)
                        and len(item) <= 4096
                        and item.startswith(("http://", "https://"))
                    ]

                    threading.Thread(
                        target=self._worker,
                        args=(url, mode, candidates),
                        daemon=True,
                    ).start()
                    body = json.dumps({"ok": True, "queued": True, "mode": mode, "candidates": len(candidates)}).encode()
                    self.send_response(202)
                except Exception as exc:
                    body = json.dumps({"ok": False, "error": str(exc)}).encode()
                    self.send_response(400)

                self._common_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _worker(self, url: str, mode: str, candidates: list[str]) -> None:
                try:
                    log(f"Richiesta dal browser: {url}")
                    if candidates:
                        log(f"Il browser ha rilevato {len(candidates)} possibili file/flussi media.")
                    download_url(url, config.output_dir, mode, log, browser_candidates=candidates)
                    log("Richiesta browser completata.")
                except Exception as exc:
                    log(f"Errore richiesta browser: {exc}")

            def log_message(self, format: str, *args) -> None:
                return

        self._server = ThreadingHTTPServer(("127.0.0.1", config.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.log(f"Connettore browser MediaGrab 0.2 attivo su http://127.0.0.1:{config.port}")

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
            self.log("Connettore browser arrestato.")
