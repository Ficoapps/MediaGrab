from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

LogFn = Callable[[str], None]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36"
)

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ts"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac"}
MANIFEST_EXTENSIONS = {".m3u8", ".mpd"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
MEDIA_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+?\.(?:mp4|webm|mkv|mov|m4v|avi|ts|mp3|m4a|aac|ogg|opus|wav|flac|m3u8|mpd|jpg|jpeg|png|webp|gif|avif)(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)


def _safe_name(name: str, fallback: str = "file") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip(" .")
    return name[:180] or fallback


def _normalize_url(value: str | None, page_url: str) -> str | None:
    if not value:
        return None
    value = value.strip().replace("\\/", "/")
    value = value.replace("\\u002F", "/").replace("\\u002f", "/")
    value = value.replace("\\u0026", "&")
    if value.startswith("//"):
        value = "https:" + value
    else:
        value = urljoin(page_url, value)
    if not value.startswith(("http://", "https://")):
        return None
    return value


def _suffix(url: str) -> str:
    return Path(urlparse(url).path).suffix.lower()


def _filename_from_url(
    url: str,
    index: int,
    content_type: str | None = None,
    fallback: str = "file",
) -> str:
    parsed = urlparse(url)
    candidate = unquote(Path(parsed.path).name)
    if candidate and "." in candidate:
        return _safe_name(candidate, fallback)
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ""
    return f"{fallback}_{index:03d}{ext}"


def _unique_http(urls: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in urls:
        if not value or not value.startswith(("http://", "https://")):
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_batch_urls(values: Iterable[str]) -> list[str]:
    """Normalizza una lista di URL per il download multiplo mantenendo l'ordine."""
    return _unique_http(value.strip() for value in values if value and value.strip())


def extract_media_from_html(page_url: str, html_text: str) -> dict[str, list[str]]:
    """Estrae URL media dichiarati nell'HTML statico, senza eseguire JavaScript."""
    soup = BeautifulSoup(html_text, "html.parser")
    images: list[str | None] = []
    videos: list[str | None] = []
    audios: list[str | None] = []

    for tag in soup.find_all("img"):
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            images.append(_normalize_url(tag.get(attr), page_url))
        srcset = tag.get("srcset") or tag.get("data-srcset")
        if srcset:
            candidates = [part.strip().split(" ")[0] for part in srcset.split(",") if part.strip()]
            if candidates:
                images.append(_normalize_url(candidates[-1], page_url))

    for audio in soup.find_all("audio"):
        for attr in ("src", "data-src", "data-audio", "data-url"):
            audios.append(_normalize_url(audio.get(attr), page_url))

    for source in soup.find_all("source"):
        src = _normalize_url(source.get("src"), page_url)
        if src:
            ext = _suffix(src)
            source_type = (source.get("type") or "").lower()
            if ext in IMAGE_EXTENSIONS or source_type.startswith("image/"):
                images.append(src)
            elif ext in AUDIO_EXTENSIONS or source_type.startswith("audio/"):
                audios.append(src)
            else:
                videos.append(src)

        srcset = source.get("srcset")
        if srcset:
            for part in srcset.split(","):
                images.append(_normalize_url(part.strip().split(" ")[0], page_url))

    for video in soup.find_all("video"):
        for attr in ("src", "data-src", "data-video", "data-url"):
            videos.append(_normalize_url(video.get(attr), page_url))

    for link in soup.find_all("a", href=True):
        href = _normalize_url(link.get("href"), page_url)
        if not href:
            continue
        ext = _suffix(href)
        if ext in AUDIO_EXTENSIONS:
            audios.append(href)
        elif ext in VIDEO_EXTENSIONS or ext in MANIFEST_EXTENSIONS:
            videos.append(href)
        elif ext in IMAGE_EXTENSIONS:
            images.append(href)

    for attrs, bucket in (
        (("property", "og:image"), images),
        (("name", "twitter:image"), images),
        (("property", "og:audio"), audios),
        (("property", "og:audio:url"), audios),
        (("property", "og:audio:secure_url"), audios),
        (("property", "og:video"), videos),
        (("property", "og:video:url"), videos),
        (("property", "og:video:secure_url"), videos),
        (("name", "twitter:player:stream"), videos),
    ):
        meta = soup.find("meta", attrs={attrs[0]: attrs[1]})
        if meta and meta.get("content"):
            bucket.append(_normalize_url(meta.get("content"), page_url))

    normalized_text = html_text.replace("\\/", "/")
    normalized_text = normalized_text.replace("\\u002F", "/").replace("\\u002f", "/")
    normalized_text = normalized_text.replace("\\u0026", "&")
    for match in MEDIA_URL_RE.findall(normalized_text):
        ext = _suffix(match)
        if ext in AUDIO_EXTENSIONS:
            audios.append(match)
        elif ext in VIDEO_EXTENSIONS or ext in MANIFEST_EXTENSIONS:
            videos.append(match)
        elif ext in IMAGE_EXTENSIONS:
            images.append(match)

    return {
        "videos": _unique_http(videos),
        "audios": _unique_http(audios),
        "images": _unique_http(images),
    }


def fetch_page_media(page_url: str, log: LogFn) -> dict[str, list[str]]:
    response = requests.get(
        page_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        timeout=25,
    )
    response.raise_for_status()
    result = extract_media_from_html(page_url, response.text)
    log(
        "HTML: "
        f"{len(result['videos'])} sorgenti video, "
        f"{len(result['audios'])} audio e "
        f"{len(result['images'])} immagini rilevate."
    )
    return result


def _download_binary(
    url: str,
    target_dir: Path,
    log: LogFn,
    index: int,
    referer: str | None = None,
) -> Path:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    with requests.get(
        url,
        headers=headers,
        timeout=30,
        stream=True,
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        filename = _filename_from_url(url, index, content_type, fallback="media")
        target = target_dir / filename
        stem, suffix = target.stem, target.suffix
        counter = 2
        while target.exists():
            target = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        with target.open("wb") as fh:
            for chunk in response.iter_content(1024 * 256):
                if chunk:
                    fh.write(chunk)
    log(f"Salvato: {target.name}")
    return target


def download_images(
    page_url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
) -> int:
    html_candidates: list[str] = []
    try:
        html_candidates = fetch_page_media(page_url, log)["images"]
    except Exception as exc:
        log(f"Analisi immagini HTML non riuscita: {exc}")

    dynamic = [u for u in (browser_candidates or []) if _suffix(u) in IMAGE_EXTENSIONS]
    clean_urls = _unique_http([*html_candidates, *dynamic])
    if not clean_urls:
        log("Nessuna immagine scaricabile rilevata.")
        return 0

    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    for index, image_url in enumerate(clean_urls, start=1):
        try:
            path = _download_binary(image_url, image_dir, log, index, referer=page_url)
            if path.stat().st_size > 0:
                saved += 1
        except Exception as exc:
            log(f"Immagine saltata: {image_url} ({exc})")
    return saved


def _ytdlp_options(
    target_dir: Path,
    log: LogFn,
    referer: str | None = None,
    audio_only: bool = False,
) -> dict:
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
            label = "audio" if audio_only else "video"
            log(f"Download {label} completato. Elaborazione finale…")

    has_ffmpeg = shutil.which("ffmpeg") is not None

    if audio_only:
        opts: dict = {
            "outtmpl": str(target_dir / "%(title).180B [%(id)s].%(ext)s"),
            "format": "bestaudio/best",
            "noplaylist": True,
            "windowsfilenames": True,
            "logger": Logger(),
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "http_headers": {"User-Agent": USER_AGENT},
        }
        if has_ffmpeg:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ]
            log("Audio: FFmpeg rilevato, conversione finale in MP3.")
        else:
            log("Audio: FFmpeg non rilevato, manterrò il miglior formato audio disponibile.")
    else:
        if not has_ffmpeg:
            log("FFmpeg non rilevato: alcuni flussi separati audio/video potrebbero non essere unibili.")
        opts = {
            "outtmpl": str(target_dir / "%(title).180B [%(id)s].%(ext)s"),
            "format": "bv*+ba/b" if has_ffmpeg else "b",
            "merge_output_format": "mp4" if has_ffmpeg else None,
            "noplaylist": True,
            "windowsfilenames": True,
            "logger": Logger(),
            "progress_hooks": [hook],
            "quiet": True,
            "no_warnings": True,
            "http_headers": {"User-Agent": USER_AGENT},
        }

    if referer:
        opts["http_headers"]["Referer"] = referer
    return opts


def _download_with_ytdlp(
    target_url: str,
    target_dir: Path,
    log: LogFn,
    referer: str | None = None,
    audio_only: bool = False,
) -> None:
    from yt_dlp import YoutubeDL

    with YoutubeDL(
        _ytdlp_options(
            target_dir,
            log,
            referer=referer,
            audio_only=audio_only,
        )
    ) as ydl:
        ydl.download([target_url])


def download_video(
    url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
) -> None:
    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    direct_ext = _suffix(url)
    if direct_ext in VIDEO_EXTENSIONS or direct_ext in MANIFEST_EXTENSIONS:
        log("URL media diretto rilevato.")
        _download_with_ytdlp(url, video_dir, log)
        return

    log("Metodo 1/3: analisi con yt-dlp…")
    first_error: Exception | None = None
    try:
        _download_with_ytdlp(url, video_dir, log)
        return
    except Exception as exc:
        first_error = exc
        log(f"yt-dlp non gestisce direttamente questa pagina: {exc}")

    log("Metodo 2/3: analisi del codice HTML…")
    html_candidates: list[str] = []
    try:
        html_candidates = fetch_page_media(url, log)["videos"]
    except Exception as exc:
        log(f"Analisi HTML non riuscita: {exc}")

    log("Metodo 3/3: sorgenti rilevate dal browser…")
    dynamic = [
        candidate
        for candidate in (browser_candidates or [])
        if _suffix(candidate) in VIDEO_EXTENSIONS or _suffix(candidate) in MANIFEST_EXTENSIONS
    ]
    if dynamic:
        log(f"Browser: {len(dynamic)} possibili sorgenti video ricevute.")
    else:
        log("Browser: nessuna sorgente dinamica ricevuta. Usa l'estensione per le pagine JavaScript.")

    candidates = _unique_http([*html_candidates, *dynamic])
    if not candidates:
        raise RuntimeError(
            "Nessuna sorgente video pubblicamente accessibile è stata rilevata. "
            "Se il video è visibile nel browser, prova tramite l'estensione MediaGrab 0.3. "
            "I contenuti protetti da DRM o controlli di accesso non vengono aggirati."
        ) from first_error

    last_error: Exception | None = None
    for index, media_url in enumerate(candidates, start=1):
        try:
            log(f"Tentativo sorgente {index}/{len(candidates)}: {media_url[:120]}")
            _download_with_ytdlp(media_url, video_dir, log, referer=url)
            return
        except Exception as exc:
            last_error = exc
            log(f"Sorgente {index} non scaricata: {exc}")

    raise RuntimeError("Le sorgenti video rilevate non sono risultate scaricabili.") from last_error


def download_audio(
    url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
) -> None:
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    direct_ext = _suffix(url)
    if (
        direct_ext in AUDIO_EXTENSIONS
        or direct_ext in VIDEO_EXTENSIONS
        or direct_ext in MANIFEST_EXTENSIONS
    ):
        log("URL media diretto rilevato: estraggo solo l'audio.")
        _download_with_ytdlp(url, audio_dir, log, audio_only=True)
        return

    log("Audio 1/3: estrazione tramite yt-dlp…")
    first_error: Exception | None = None
    try:
        _download_with_ytdlp(url, audio_dir, log, audio_only=True)
        return
    except Exception as exc:
        first_error = exc
        log(f"yt-dlp non gestisce direttamente l'audio di questa pagina: {exc}")

    log("Audio 2/3: analisi del codice HTML…")
    html_candidates: list[str] = []
    try:
        media = fetch_page_media(url, log)
        html_candidates = [*media["audios"], *media["videos"]]
    except Exception as exc:
        log(f"Analisi HTML non riuscita: {exc}")

    log("Audio 3/3: sorgenti rilevate dal browser…")
    dynamic = [
        candidate
        for candidate in (browser_candidates or [])
        if (
            _suffix(candidate) in AUDIO_EXTENSIONS
            or _suffix(candidate) in VIDEO_EXTENSIONS
            or _suffix(candidate) in MANIFEST_EXTENSIONS
        )
    ]
    if dynamic:
        log(f"Browser: {len(dynamic)} possibili sorgenti audio/video ricevute.")
    else:
        log("Browser: nessuna sorgente dinamica ricevuta.")

    candidates = _unique_http([*html_candidates, *dynamic])
    if not candidates:
        raise RuntimeError(
            "Nessuna sorgente audio accessibile è stata rilevata. "
            "Se il contenuto è riproducibile nel browser, prova con l'estensione MediaGrab 0.3."
        ) from first_error

    last_error: Exception | None = None
    for index, media_url in enumerate(candidates, start=1):
        try:
            log(f"Tentativo audio {index}/{len(candidates)}: {media_url[:120]}")
            _download_with_ytdlp(
                media_url,
                audio_dir,
                log,
                referer=url,
                audio_only=True,
            )
            return
        except Exception as exc:
            last_error = exc
            log(f"Sorgente audio {index} non scaricata: {exc}")

    raise RuntimeError("Le sorgenti audio rilevate non sono risultate scaricabili.") from last_error


def download_url(
    url: str,
    output: str | Path,
    mode: str,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
) -> None:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Inserisci un URL http:// o https:// valido.")

    output_dir = Path(output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = _unique_http(browser_candidates or [])
    log(f"URL: {url}")
    log(f"Cartella: {output_dir}")
    log(f"Modalità: {mode}")
    if candidates:
        log(f"Sorgenti browser ricevute: {len(candidates)}")

    errors: list[str] = []

    if mode in ("video", "all"):
        try:
            download_video(url, output_dir, log, browser_candidates=candidates)
        except Exception as exc:
            errors.append(f"video: {exc}")
            log(f"Video non scaricato: {exc}")

    if mode == "audio":
        try:
            download_audio(url, output_dir, log, browser_candidates=candidates)
        except Exception as exc:
            errors.append(f"audio: {exc}")
            log(f"Audio non scaricato: {exc}")

    if mode in ("images", "all"):
        try:
            count = download_images(url, output_dir, log, browser_candidates=candidates)
            log(f"Immagini scaricate: {count}")
        except Exception as exc:
            errors.append(f"immagini: {exc}")
            log(f"Immagini non scaricate: {exc}")

    if errors and mode != "all":
        raise RuntimeError("; ".join(errors))
    if errors and mode == "all" and len(errors) == 2:
        raise RuntimeError("; ".join(errors))
