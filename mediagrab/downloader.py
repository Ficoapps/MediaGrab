from __future__ import annotations

import ipaddress
import mimetypes
import re
import shutil
import socket
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import __version__
from .constants import VALID_AUDIO_QUALITIES, VALID_MODES, VALID_VIDEO_QUALITIES

LogFn = Callable[[str], None]
PageMedia = dict[str, list[str]]
PageMediaProvider = Callable[[], PageMedia]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153 Safari/537.36"
)

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ts"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac"}
MANIFEST_EXTENSIONS = {".m3u8", ".mpd"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp"}
MAX_HTML_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 200 * 1024 * 1024
MAX_REDIRECTS = 5
MAX_IMAGE_WORKERS = 4
MAX_IMAGE_CANDIDATES = 250
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MEDIA_URL_RE = re.compile(
    r"https?://[^\s\"'<>]+?\."
    r"(?:mp4|webm|mkv|mov|m4v|avi|ts|mp3|m4a|aac|ogg|opus|wav|flac|"
    r"m3u8|mpd|jpg|jpeg|png|webp|gif|avif)(?:\?[^\s\"'<>]*)?",
    re.IGNORECASE,
)


class DownloadCancelled(RuntimeError):
    """Raised when the user requests cooperative cancellation."""


def _raise_if_cancelled(cancel_event: threading.Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise DownloadCancelled("Download annullato dall'utente")


def _media_kind_from_content_type(content_type: str) -> str | None:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime.startswith("image/"):
        return "images"
    if mime.startswith("video/"):
        return "videos"
    if mime.startswith("audio/"):
        return "audios"
    return None


@dataclass
class DownloadResult:
    succeeded: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def partial(self) -> bool:
        return bool(self.succeeded and self.errors)

    @property
    def ok(self) -> bool:
        return bool(self.succeeded) and not self.errors


def _safe_name(name: str, fallback: str = "file") -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name).strip(" .")
    name = name[:180] or fallback
    stem = name.split(".", 1)[0].upper()
    if stem in WINDOWS_RESERVED_NAMES:
        name = f"_{name}"
    return name


def _normalize_url(value: str | None, page_url: str) -> str | None:
    if not value:
        return None
    value = value.strip().replace("\\/", "/")
    value = value.replace("\\u002F", "/").replace("\\u002f", "/")
    value = value.replace("\\u0026", "&")
    value = urljoin(page_url, value)
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
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
    return _safe_name(f"{fallback}_{index:03d}{ext}", fallback)


def _unique_http(urls: Iterable[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in urls:
        if not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_batch_urls(values: Iterable[str]) -> list[str]:
    """Normalizza URL validi mantenendo ordine e rimuovendo duplicati."""
    return _unique_http(value.strip() for value in values if value and value.strip())


def validate_public_http_url(url: str) -> str:
    """Rifiuta URL non HTTP(S), credenziali inline e destinazioni non pubbliche."""
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL http:// o https:// non valido")
    if parsed.username or parsed.password:
        raise ValueError("Le credenziali nell'URL non sono consentite")

    host = parsed.hostname.rstrip(".")
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not literal_ip.is_global:
            raise ValueError("Gli indirizzi IP locali o privati non sono consentiti")
        return url

    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise ValueError("localhost non è consentito")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Host non risolvibile: {host}") from exc

    if not addresses:
        raise ValueError(f"Host non risolvibile: {host}")

    for address in addresses:
        ip_text = address[4][0].split("%", 1)[0]
        try:
            resolved_ip = ipaddress.ip_address(ip_text)
        except ValueError as exc:
            raise ValueError("Indirizzo IP risolto non valido") from exc
        if not resolved_ip.is_global:
            raise ValueError("La destinazione risolve a una rete locale o privata")
    return url


def _request_public(
    url: str,
    *,
    headers: dict[str, str],
    timeout: int,
    stream: bool,
) -> requests.Response:
    """Segue pochi redirect validando ogni destinazione prima della connessione."""
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_http_url(current)
        response = requests.get(
            current,
            headers=headers,
            timeout=timeout,
            stream=stream,
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise RuntimeError("Redirect senza destinazione")
            current = urljoin(current, location)
            continue
        return response
    raise RuntimeError("Troppi redirect HTTP")


def extract_media_from_html(page_url: str, html_text: str) -> PageMedia:
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
            candidates = [
                part.strip().split(" ")[0]
                for part in srcset.split(",")
                if part.strip()
            ]
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


def fetch_page_media(
    page_url: str,
    log: LogFn,
    cancel_event: threading.Event | None = None,
) -> PageMedia:
    _raise_if_cancelled(cancel_event)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"}
    with _request_public(
        page_url,
        headers=headers,
        timeout=25,
        stream=True,
    ) as response:
        response.raise_for_status()

        media_kind = _media_kind_from_content_type(
            response.headers.get("Content-Type", "")
        )
        if media_kind:
            result: PageMedia = {"videos": [], "audios": [], "images": []}
            result[media_kind].append(page_url)
            log(f"URL media diretto rilevato dal Content-Type: {media_kind}.")
            return result

        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_HTML_BYTES:
            raise RuntimeError("Pagina HTML troppo grande da analizzare")

        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(256 * 1024):
            _raise_if_cancelled(cancel_event)
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_HTML_BYTES:
                raise RuntimeError("Pagina HTML troppo grande da analizzare")
            chunks.append(chunk)
        encoding = response.encoding or "utf-8"
        html_text = b"".join(chunks).decode(encoding, errors="replace")

    _raise_if_cancelled(cancel_event)
    result = extract_media_from_html(page_url, html_text)
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
    required_content_prefix: str | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    _raise_if_cancelled(cancel_event)
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer

    with _request_public(url, headers=headers, timeout=30, stream=True) as response:
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        normalized_type = content_type.split(";", 1)[0].strip().lower()
        if required_content_prefix:
            has_expected_type = normalized_type.startswith(required_content_prefix)
            known_extension = (
                required_content_prefix == "image/" and _suffix(url) in IMAGE_EXTENSIONS
            )
            if not has_expected_type and not (not normalized_type and known_extension):
                raise RuntimeError(
                    f"Content-Type inatteso: {content_type or 'non dichiarato'}"
                )

        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_IMAGE_BYTES:
            raise RuntimeError("File immagine troppo grande")

        filename = _filename_from_url(url, index, content_type, fallback="media")
        base_target = target_dir / filename
        stem, suffix = base_target.stem, base_target.suffix
        counter = 1

        while True:
            target = (
                base_target
                if counter == 1
                else target_dir / f"{stem}_{counter}{suffix}"
            )
            if target.exists():
                counter += 1
                continue
            temp_target = target.with_name(target.name + ".part")
            try:
                fh = temp_target.open("xb")
                break
            except FileExistsError:
                counter += 1

        total = 0
        try:
            with fh:
                for chunk in response.iter_content(256 * 1024):
                    _raise_if_cancelled(cancel_event)
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_IMAGE_BYTES:
                        raise RuntimeError("File immagine troppo grande")
                    fh.write(chunk)
            _raise_if_cancelled(cancel_event)
            temp_target.replace(target)
        except Exception:
            temp_target.unlink(missing_ok=True)
            raise

    log(f"Salvato: {target.name}")
    return target


def _get_page_media(
    page_url: str,
    log: LogFn,
    provider: PageMediaProvider | None,
    cancel_event: threading.Event | None = None,
) -> PageMedia:
    _raise_if_cancelled(cancel_event)
    return provider() if provider else fetch_page_media(
        page_url,
        log,
        cancel_event=cancel_event,
    )


def download_images(
    page_url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
    page_media_provider: PageMediaProvider | None = None,
    cancel_event: threading.Event | None = None,
) -> int:
    _raise_if_cancelled(cancel_event)
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    if _suffix(page_url) in IMAGE_EXTENSIONS:
        path = _download_binary(
            page_url,
            image_dir,
            log,
            1,
            required_content_prefix="image/",
            cancel_event=cancel_event,
        )
        return 1 if path.stat().st_size > 0 else 0

    html_candidates: list[str] = []
    try:
        html_candidates = _get_page_media(
            page_url,
            log,
            page_media_provider,
            cancel_event=cancel_event,
        )["images"]
    except DownloadCancelled:
        raise
    except Exception as exc:
        log(f"Analisi immagini HTML non riuscita: {exc}")

    known_media_extensions = (
        IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | MANIFEST_EXTENSIONS
    )
    dynamic = [
        u
        for u in (browser_candidates or [])
        if _suffix(u) in IMAGE_EXTENSIONS or _suffix(u) not in known_media_extensions
    ]
    clean_urls = _unique_http([*html_candidates, *dynamic])
    if len(clean_urls) > MAX_IMAGE_CANDIDATES:
        log(
            f"Immagini: limitate alle prime {MAX_IMAGE_CANDIDATES} "
            f"sorgenti su {len(clean_urls)} rilevate."
        )
        clean_urls = clean_urls[:MAX_IMAGE_CANDIDATES]

    if not clean_urls:
        log("Nessuna immagine scaricabile rilevata.")
        return 0

    saved = 0

    def worker(item: tuple[int, str]) -> bool:
        index, image_url = item
        path = _download_binary(
            image_url,
            image_dir,
            log,
            index,
            referer=page_url,
            required_content_prefix="image/",
            cancel_event=cancel_event,
        )
        return path.stat().st_size > 0

    max_workers = min(MAX_IMAGE_WORKERS, len(clean_urls))
    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="mediagrab-image",
    ) as executor:
        future_to_url = {
            executor.submit(worker, item): item[1]
            for item in enumerate(clean_urls, start=1)
        }
        for future in as_completed(future_to_url):
            try:
                if future.result():
                    saved += 1
            except DownloadCancelled:
                for pending in future_to_url:
                    pending.cancel()
                raise
            except Exception as exc:
                image_url = future_to_url[future]
                log(f"Immagine saltata: {image_url} ({exc})")

    return saved


def _normalized_video_quality(value: str) -> str:
    value = str(value or "best").lower()
    return value if value in VALID_VIDEO_QUALITIES else "best"


def _normalized_audio_quality(value: str) -> str:
    value = str(value or "best").lower()
    return value if value in VALID_AUDIO_QUALITIES else "best"


def _video_format_selector(
    video_quality: str,
    audio_quality: str,
    has_ffmpeg: bool,
) -> str:
    video_quality = _normalized_video_quality(video_quality)
    audio_quality = _normalized_audio_quality(audio_quality)

    if not has_ffmpeg:
        if video_quality == "best":
            return "b"
        return f"b[height<={video_quality}]"

    video = "bv*" if video_quality == "best" else f"bv*[height<={video_quality}]"
    combined = "b" if video_quality == "best" else f"b[height<={video_quality}]"

    if audio_quality == "best":
        return f"{video}+ba/{combined}"

    return f"{video}+ba[abr<={audio_quality}]/{video}+ba/{combined}"


def _audio_format_selector(audio_quality: str) -> str:
    audio_quality = _normalized_audio_quality(audio_quality)
    if audio_quality == "best":
        return "bestaudio/best"
    return f"bestaudio[abr<={audio_quality}]/bestaudio/best"


def _ytdlp_options(
    target_dir: Path,
    log: LogFn,
    referer: str | None = None,
    audio_only: bool = False,
    video_quality: str = "best",
    audio_quality: str = "best",
    cancel_event: threading.Event | None = None,
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
        _raise_if_cancelled(cancel_event)
        if data.get("status") == "finished":
            label = "audio" if audio_only else "video"
            log(f"Download {label} completato. Elaborazione finale…")

    has_ffmpeg = shutil.which("ffmpeg") is not None
    video_quality = _normalized_video_quality(video_quality)
    audio_quality = _normalized_audio_quality(audio_quality)

    opts: dict = {
        "outtmpl": str(target_dir / "%(title).180B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "windowsfilenames": True,
        "logger": Logger(),
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "http_headers": {"User-Agent": USER_AGENT},
    }

    if audio_only:
        opts["format"] = (
            "bestaudio/best" if has_ffmpeg else _audio_format_selector(audio_quality)
        )
        if has_ffmpeg:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0" if audio_quality == "best" else audio_quality,
                }
            ]
            quality_label = (
                "migliore disponibile" if audio_quality == "best" else f"{audio_quality} kbps"
            )
            log(f"Audio: FFmpeg rilevato, conversione finale in MP3 ({quality_label}).")
        else:
            quality_label = (
                "migliore disponibile" if audio_quality == "best" else f"fino a {audio_quality} kbps"
            )
            log(f"Audio: FFmpeg non rilevato, formato originale ({quality_label}).")
    else:
        if not has_ffmpeg:
            log("FFmpeg non rilevato: alcuni flussi separati audio/video potrebbero non essere unibili.")
            if audio_quality != "best":
                log("Senza FFmpeg non posso scegliere separatamente il bitrate audio di un video già combinato.")
        opts["format"] = _video_format_selector(video_quality, audio_quality, has_ffmpeg)
        if has_ffmpeg:
            opts["merge_output_format"] = "mp4"

    if referer:
        opts["http_headers"]["Referer"] = referer
    return opts


def _download_with_ytdlp(
    target_url: str,
    target_dir: Path,
    log: LogFn,
    referer: str | None = None,
    audio_only: bool = False,
    video_quality: str = "best",
    audio_quality: str = "best",
    cancel_event: threading.Event | None = None,
) -> None:
    _raise_if_cancelled(cancel_event)
    validate_public_http_url(target_url)

    from yt_dlp import YoutubeDL

    try:
        with YoutubeDL(
            _ytdlp_options(
                target_dir,
                log,
                referer=referer,
                audio_only=audio_only,
                video_quality=video_quality,
                audio_quality=audio_quality,
                cancel_event=cancel_event,
            )
        ) as ydl:
            ydl.download([target_url])
    except Exception as exc:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled("Download annullato dall'utente") from exc
        raise

    _raise_if_cancelled(cancel_event)


def _try_detected_candidates(
    candidates: list[str],
    *,
    target_dir: Path,
    log: LogFn,
    referer: str,
    audio_only: bool,
    video_quality: str,
    audio_quality: str,
    label: str,
    cancel_event: threading.Event | None = None,
) -> None:
    last_error: Exception | None = None
    for index, media_url in enumerate(candidates, start=1):
        _raise_if_cancelled(cancel_event)
        try:
            log(f"Tentativo {label} {index}/{len(candidates)}: {media_url[:120]}")
            _download_with_ytdlp(
                media_url,
                target_dir,
                log,
                referer=referer,
                audio_only=audio_only,
                video_quality=video_quality,
                audio_quality=audio_quality,
                cancel_event=cancel_event,
            )
            return
        except DownloadCancelled:
            raise
        except Exception as exc:
            last_error = exc
            log(f"Sorgente {label} {index} non scaricata: {exc}")
    raise RuntimeError(f"Le sorgenti {label} rilevate non sono risultate scaricabili.") from last_error


def download_video(
    url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
    video_quality: str = "best",
    audio_quality: str = "best",
    page_media_provider: PageMediaProvider | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    _raise_if_cancelled(cancel_event)
    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    direct_ext = _suffix(url)
    if direct_ext in VIDEO_EXTENSIONS or direct_ext in MANIFEST_EXTENSIONS:
        log("URL media diretto rilevato.")
        _download_with_ytdlp(
            url,
            video_dir,
            log,
            video_quality=video_quality,
            audio_quality=audio_quality,
            cancel_event=cancel_event,
        )
        return

    log("Metodo 1/3: analisi con yt-dlp…")
    first_error: Exception | None = None
    try:
        _download_with_ytdlp(
            url,
            video_dir,
            log,
            video_quality=video_quality,
            audio_quality=audio_quality,
            cancel_event=cancel_event,
        )
        return
    except DownloadCancelled:
        raise
    except Exception as exc:
        first_error = exc
        log(f"yt-dlp non gestisce direttamente questa pagina: {exc}")

    log("Metodo 2/3: analisi del codice HTML…")
    html_candidates: list[str] = []
    try:
        html_candidates = _get_page_media(
            url,
            log,
            page_media_provider,
            cancel_event=cancel_event,
        )["videos"]
    except DownloadCancelled:
        raise
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
            f"Se il video è visibile nel browser, prova tramite l'estensione MediaGrab {__version__}. "
            "I contenuti protetti da DRM o controlli di accesso non vengono aggirati."
        ) from first_error

    _try_detected_candidates(
        candidates,
        target_dir=video_dir,
        log=log,
        referer=url,
        audio_only=False,
        video_quality=video_quality,
        audio_quality=audio_quality,
        label="video",
        cancel_event=cancel_event,
    )


def download_audio(
    url: str,
    output_dir: Path,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
    audio_quality: str = "best",
    page_media_provider: PageMediaProvider | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    _raise_if_cancelled(cancel_event)
    audio_dir = output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    direct_ext = _suffix(url)
    if (
        direct_ext in AUDIO_EXTENSIONS
        or direct_ext in VIDEO_EXTENSIONS
        or direct_ext in MANIFEST_EXTENSIONS
    ):
        log("URL media diretto rilevato: estraggo solo l'audio.")
        _download_with_ytdlp(
            url,
            audio_dir,
            log,
            audio_only=True,
            audio_quality=audio_quality,
            cancel_event=cancel_event,
        )
        return

    log("Audio 1/3: estrazione tramite yt-dlp…")
    first_error: Exception | None = None
    try:
        _download_with_ytdlp(
            url,
            audio_dir,
            log,
            audio_only=True,
            audio_quality=audio_quality,
            cancel_event=cancel_event,
        )
        return
    except DownloadCancelled:
        raise
    except Exception as exc:
        first_error = exc
        log(f"yt-dlp non gestisce direttamente l'audio di questa pagina: {exc}")

    log("Audio 2/3: analisi del codice HTML…")
    html_candidates: list[str] = []
    try:
        media = _get_page_media(
            url,
            log,
            page_media_provider,
            cancel_event=cancel_event,
        )
        html_candidates = [*media["audios"], *media["videos"]]
    except DownloadCancelled:
        raise
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
            f"Se il contenuto è riproducibile nel browser, prova con l'estensione MediaGrab {__version__}."
        ) from first_error

    _try_detected_candidates(
        candidates,
        target_dir=audio_dir,
        log=log,
        referer=url,
        audio_only=True,
        video_quality="best",
        audio_quality=audio_quality,
        label="audio",
        cancel_event=cancel_event,
    )


def download_url(
    url: str,
    output: str | Path,
    mode: str,
    log: LogFn,
    browser_candidates: Iterable[str] | None = None,
    video_quality: str = "best",
    audio_quality: str = "best",
    cancel_event: threading.Event | None = None,
) -> DownloadResult:
    _raise_if_cancelled(cancel_event)
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Inserisci un URL http:// o https:// valido.")
    if mode not in VALID_MODES:
        raise ValueError(f"Modalità non valida: {mode}")

    output_dir = Path(output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = _unique_http(browser_candidates or [])
    log(f"URL: {url}")
    log(f"Cartella: {output_dir}")
    log(f"Modalità: {mode}")
    log(f"Qualità video: {_normalized_video_quality(video_quality)}")
    log(f"Qualità audio: {_normalized_audio_quality(audio_quality)}")
    if candidates:
        log(f"Sorgenti browser ricevute: {len(candidates)}")

    result = DownloadResult()
    page_media_cache: PageMedia | None = None

    def page_media_provider() -> PageMedia:
        nonlocal page_media_cache
        _raise_if_cancelled(cancel_event)
        if page_media_cache is None:
            page_media_cache = fetch_page_media(
                url,
                log,
                cancel_event=cancel_event,
            )
        return page_media_cache

    provider = page_media_provider if mode == "all" else None

    if mode in {"video", "all"}:
        try:
            download_video(
                url,
                output_dir,
                log,
                browser_candidates=candidates,
                video_quality=video_quality,
                audio_quality=audio_quality,
                page_media_provider=provider,
                cancel_event=cancel_event,
            )
            result.succeeded.append("video")
        except DownloadCancelled:
            raise
        except Exception as exc:
            result.errors["video"] = str(exc)
            log(f"Video non scaricato: {exc}")

    if mode == "audio":
        try:
            download_audio(
                url,
                output_dir,
                log,
                browser_candidates=candidates,
                audio_quality=audio_quality,
                cancel_event=cancel_event,
            )
            result.succeeded.append("audio")
        except DownloadCancelled:
            raise
        except Exception as exc:
            result.errors["audio"] = str(exc)
            log(f"Audio non scaricato: {exc}")

    if mode in {"images", "all"}:
        try:
            count = download_images(
                url,
                output_dir,
                log,
                browser_candidates=candidates,
                page_media_provider=provider,
                cancel_event=cancel_event,
            )
            if count <= 0:
                raise RuntimeError("Nessuna immagine scaricabile rilevata")
            result.succeeded.append("images")
            log(f"Immagini scaricate: {count}")
        except DownloadCancelled:
            raise
        except Exception as exc:
            result.errors["images"] = str(exc)
            log(f"Immagini non scaricate: {exc}")

    if not result.succeeded:
        raise RuntimeError("; ".join(f"{key}: {value}" for key, value in result.errors.items()))
    if mode != "all" and result.errors:
        raise RuntimeError("; ".join(f"{key}: {value}" for key, value in result.errors.items()))
    return result
