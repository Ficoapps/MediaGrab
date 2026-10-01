from __future__ import annotations

import hmac
import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from . import __version__
from .config import AppConfig
from .constants import VALID_AUDIO_QUALITIES, VALID_MODES, VALID_VIDEO_QUALITIES
from .downloader import download_url, validate_public_http_url

LogFn = Callable[[str], None]
MAX_WORKERS = 3
MAX_PENDING_DOWNLOADS = 8
MAX_CANDIDATES = 100
MAX_BODY_BYTES = 512_000
ALLOWED_ORIGIN_PREFIXES = (
    "chrome-extension://",
    "edge-extension://",
    "moz-extension://",
)


def is_extension_origin(origin: str) -> bool:
    return bool(origin) and origin.startswith(ALLOWED_ORIGIN_PREFIXES)


class LocalServer:
    def __init__(self, config: AppConfig, log: LogFn):
        self.config = config
        self.log = log
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._pending_slots: threading.BoundedSemaphore | None = None
        self._session_token = ""

    @property
    def running(self) -> bool:
        return self._server is not None

    def start(self) -> None:
        if self.running:
            return

        self._session_token = secrets.token_urlsafe(32)
        self._executor = ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="mediagrab-download",
        )
        self._pending_slots = threading.BoundedSemaphore(MAX_PENDING_DOWNLOADS)

        config = self.config
        log = self.log
        token = self._session_token
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _origin(self) -> str:
                return self.headers.get("Origin", "")

            def _origin_allowed(self) -> bool:
                origin = self._origin()
                return not origin or is_extension_origin(origin)

            def _common_headers(self) -> None:
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, X-MediaGrab-Token, X-MediaGrab-Client",
                )
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                origin = self._origin()
                if is_extension_origin(origin):
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")

            def _send_json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self._common_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):  # noqa: N802
                if not is_extension_origin(self._origin()):
                    self._send_json(403, {"ok": False, "error": "Origin non autorizzata"})
                    return
                self.send_response(204)
                self._common_headers()
                self.end_headers()

            def do_GET(self):  # noqa: N802
                if self.path != "/health":
                    self._send_json(404, {"ok": False, "error": "Not found"})
                    return

                if not self._origin_allowed():
                    self._send_json(403, {"ok": False, "error": "Origin non autorizzata"})
                    return

                payload = {"ok": True, "app": "MediaGrab", "version": __version__}
                if self.headers.get("X-MediaGrab-Client") == "extension":
                    payload["session_token"] = token
                self._send_json(200, payload)

            def do_POST(self):  # noqa: N802
                if self.path != "/download":
                    self._send_json(404, {"ok": False, "error": "Not found"})
                    return

                if not self._origin_allowed():
                    self._send_json(403, {"ok": False, "error": "Origin non autorizzata"})
                    return

                content_type = self.headers.get("Content-Type", "")
                if not content_type.lower().startswith("application/json"):
                    self._send_json(415, {"ok": False, "error": "Content-Type non supportato"})
                    return

                supplied_token = self.headers.get("X-MediaGrab-Token", "")
                if not supplied_token or not hmac.compare_digest(supplied_token, token):
                    self._send_json(403, {"ok": False, "error": "Token MediaGrab non valido"})
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self._send_json(400, {"ok": False, "error": "Content-Length non valido"})
                    return

                if length <= 0 or length > MAX_BODY_BYTES:
                    self._send_json(413, {"ok": False, "error": "Richiesta troppo grande o vuota"})
                    return

                slot = outer._pending_slots
                executor = outer._executor
                if slot is None or executor is None:
                    self._send_json(503, {"ok": False, "error": "Server non disponibile"})
                    return
                if not slot.acquire(blocking=False):
                    self._send_json(429, {"ok": False, "error": "Coda download piena"})
                    return

                try:
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("Payload JSON non valido")

                    url = str(payload.get("url", "")).strip()
                    validate_public_http_url(url)

                    mode = str(payload.get("mode") or config.mode)
                    video_quality = str(payload.get("video_quality") or config.video_quality)
                    audio_quality = str(payload.get("audio_quality") or config.audio_quality)

                    if mode not in VALID_MODES:
                        mode = config.mode
                    if video_quality not in VALID_VIDEO_QUALITIES:
                        video_quality = config.video_quality
                    if audio_quality not in VALID_AUDIO_QUALITIES:
                        audio_quality = config.audio_quality

                    raw_candidates = payload.get("candidates") or []
                    if not isinstance(raw_candidates, list):
                        raw_candidates = []

                    candidates: list[str] = []
                    for item in raw_candidates[:MAX_CANDIDATES]:
                        if not isinstance(item, str) or len(item) > 4096:
                            continue
                        candidate = item.strip()
                        try:
                            validate_public_http_url(candidate)
                        except ValueError:
                            continue
                        candidates.append(candidate)

                    output_dir = config.output_dir
                    executor.submit(
                        self._worker,
                        url,
                        output_dir,
                        mode,
                        candidates,
                        video_quality,
                        audio_quality,
                        slot,
                    )

                    self._send_json(
                        202,
                        {
                            "ok": True,
                            "queued": True,
                            "mode": mode,
                            "candidates": len(candidates),
                            "video_quality": video_quality,
                            "audio_quality": audio_quality,
                        },
                    )
                except Exception as exc:
                    slot.release()
                    self._send_json(400, {"ok": False, "error": str(exc)})

            def _worker(
                self,
                url: str,
                output_dir: str,
                mode: str,
                candidates: list[str],
                video_quality: str,
                audio_quality: str,
                slot: threading.BoundedSemaphore,
            ) -> None:
                try:
                    log(f"Richiesta dal browser: {url}")
                    if candidates:
                        log(
                            f"Il browser ha rilevato "
                            f"{len(candidates)} possibili file/flussi media."
                        )

                    result = download_url(
                        url,
                        output_dir,
                        mode,
                        log,
                        browser_candidates=candidates,
                        video_quality=video_quality,
                        audio_quality=audio_quality,
                    )
                    if result.partial:
                        log(
                            "Richiesta browser completata parzialmente: "
                            + "; ".join(
                                f"{kind}: {error}" for kind, error in result.errors.items()
                            )
                        )
                    else:
                        log("Richiesta browser completata.")
                except Exception as exc:
                    log(f"Errore richiesta browser: {exc}")
                finally:
                    slot.release()

            def log_message(self, format: str, *args) -> None:
                return

        try:
            self._server = ThreadingHTTPServer(
                ("127.0.0.1", config.port),
                Handler,
            )
        except Exception:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
            self._pending_slots = None
            raise

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        self.log(
            f"Connettore browser MediaGrab {__version__} attivo su "
            f"http://127.0.0.1:{config.port}"
        )

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self._thread = None
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        self._pending_slots = None
        self._session_token = ""
        self.log("Connettore browser arrestato.")
