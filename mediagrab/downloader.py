from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

LogFn = Callable[[str], None]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36"
)


def _safe_name(name: str, fallback: str = "file") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip(" .")
    return name[:180] or fallback


def _filename_from_url(url: str, index: int, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    candidate = Path(parsed.path).name
    if candidate and "." in candidate:
        return _safe_name(candidate)
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".jpg"
    return f"image_{index:03d}{ext}"


def download_images(page_url: str, output_dir: Path, log: LogFn) -> int:
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(page_url, headers=headers, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    urls: list[str] = []

    for tag in soup.find_all("img"):
        for attr in ("src", "data-src", "data-original"):
            value = tag.get(attr)
            if value:
                urls.append(urljoin(page_url, value))
        srcset = tag.get("srcset")
        if srcset:
            parts = [part.strip().split(" ")[0] for part in srcset.split(",") if part.strip()]
            if parts:
                urls.append(urljoin(page_url, parts[-1]))

    for meta_key in (("property", "og:image"), ("name", "twitter:image")):
        meta = soup.find("meta", attrs={meta_key[0]: meta_key[1]})
        if meta and meta.get("content"):
            urls.append(urljoin(page_url, meta["content"]))

    # Ordine stabile, niente duplicati, niente data/blob URL.
    clean_urls = list(dict.fromkeys(u for u in urls if u.startswith(("http://", "https://"))))
    if not clean_urls:
        log("Nessuna immagine HTML trovata nella pagina.")
        return 0

    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for index, image_url in enumerate(clean_urls, start=1):
        try:
            r = requests.get(image_url, headers={**headers, "Referer": page_url}, timeout=20, stream=True)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "")
            if content_type and not content_type.lower().startswith("image/"):
                continue
            filename = _filename_from_url(image_url, index, content_type)
            target = image_dir / filename
            stem, suffix = target.stem, target.suffix
            counter = 2
            while target.exists():
                target = image_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            with target.open("wb") as fh:
                for chunk in r.iter_content(1024 * 128):
                    if chunk:
                        fh.write(chunk)
            saved += 1
            log(f"Immagine salvata: {target.name}")
        except Exception as exc:
            log(f"Immagine saltata: {image_url} ({exc})")

    return saved


def download_video(url: str, output_dir: Path, log: LogFn) -> None:
    from yt_dlp import YoutubeDL

    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    class Logger:
        def debug(self, msg: str) -> None:
            if msg.startswith("[download]") and ("%" in msg or "Destination" in msg):
                log(msg)

        def info(self, msg: str) -> None:
            log(msg)

        def warning(self, msg: str) -> None:
            log(f"Avviso: {msg}")

        def error(self, msg: str) -> None:
            log(f"Errore yt-dlp: {msg}")

    def hook(data: dict) -> None:
        if data.get("status") == "finished":
            log("Download video completato. Elaborazione finale…")

    has_ffmpeg = shutil.which("ffmpeg") is not None
    if not has_ffmpeg:
        log("FFmpeg non rilevato: userò il miglior formato singolo disponibile.")

    opts = {
        "outtmpl": str(video_dir / "%(title).180B [%(id)s].%(ext)s"),
        "format": "bv*+ba/b" if has_ffmpeg else "b[ext=mp4]/b",
        "merge_output_format": "mp4" if has_ffmpeg else None,
        "noplaylist": True,
        "windowsfilenames": True,
        "logger": Logger(),
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
    }

    log("Analisi video con yt-dlp…")
    with YoutubeDL(opts) as ydl:
        ydl.download([url])


def download_url(url: str, output: str | Path, mode: str, log: LogFn) -> None:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Inserisci un URL http:// o https:// valido.")

    output_dir = Path(output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    log(f"URL: {url}")
    log(f"Cartella: {output_dir}")
    log(f"Modalità: {mode}")

    errors: list[str] = []

    if mode in ("video", "all"):
        try:
            download_video(url, output_dir, log)
        except Exception as exc:
            errors.append(f"video: {exc}")
            log(f"Video non scaricato: {exc}")

    if mode in ("images", "all"):
        try:
            count = download_images(url, output_dir, log)
            log(f"Immagini scaricate: {count}")
        except Exception as exc:
            errors.append(f"immagini: {exc}")
            log(f"Immagini non scaricate: {exc}")

    if errors and mode != "all":
        raise RuntimeError("; ".join(errors))
    if errors and mode == "all" and len(errors) == 2:
        raise RuntimeError("; ".join(errors))
