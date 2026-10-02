import json
import socket
import threading
import time

import pytest

import requests

import mediagrab.config as config_module
import mediagrab.downloader as downloader
import mediagrab.server as server_module
from mediagrab.config import AppConfig
from mediagrab.downloader import (
    DownloadCancelled,
    DownloadResult,
    _audio_format_selector,
    _download_with_ytdlp,
    _media_kind_from_content_type,
    _safe_name,
    _video_format_selector,
    _ytdlp_options,
    download_images,
    download_url,
    extract_media_from_html,
    normalize_batch_urls,
    validate_public_http_url,
)
from mediagrab.server import LocalServer, is_extension_origin


def test_safe_name_removes_windows_forbidden_chars():
    assert _safe_name('a:b*c?.mp4') == 'a_b_c_.mp4'


def test_safe_name_avoids_windows_reserved_names():
    assert _safe_name("CON.txt") == "_CON.txt"
    assert _safe_name("nul.mp3") == "_nul.mp3"


def test_extract_static_video_audio_and_image_urls():
    html = '''
    <html><head>
      <meta property="og:video" content="https://cdn.example/video/master.m3u8">
      <meta property="og:audio" content="https://cdn.example/audio/theme.mp3">
      <meta property="og:image" content="/cover.jpg">
    </head><body>
      <video src="/movie.mp4"><source src="https://cdn.example/backup.webm"></video>
      <audio src="/speech.m4a"></audio>
      <img src="/photo.png">
    </body></html>
    '''
    media = extract_media_from_html("https://example.test/page", html)

    assert "https://example.test/movie.mp4" in media["videos"]
    assert "https://cdn.example/backup.webm" in media["videos"]
    assert "https://cdn.example/video/master.m3u8" in media["videos"]
    assert "https://example.test/speech.m4a" in media["audios"]
    assert "https://cdn.example/audio/theme.mp3" in media["audios"]
    assert "https://example.test/photo.png" in media["images"]
    assert "https://example.test/cover.jpg" in media["images"]


def test_extract_script_embedded_media_urls():
    html = (
        '<script>'
        'const source="https://media.example/path/stream.mpd?token=abc";'
        'const audio="https://media.example/path/audio.opus?token=xyz";'
        '</script>'
    )
    media = extract_media_from_html("https://example.test/page", html)

    assert "https://media.example/path/stream.mpd?token=abc" in media["videos"]
    assert "https://media.example/path/audio.opus?token=xyz" in media["audios"]


def test_normalize_batch_urls_keeps_order_and_removes_duplicates():
    urls = normalize_batch_urls(
        [
            " https://example.test/a ",
            "",
            "https://example.test/b",
            "https://example.test/a",
            "not-a-url",
        ]
    )

    assert urls == [
        "https://example.test/a",
        "https://example.test/b",
    ]


def test_video_quality_format_selector():
    assert _video_format_selector("1080", "best", True) == (
        "bv*[height<=1080]+ba/b[height<=1080]"
    )
    assert _video_format_selector("720", "192", True) == (
        "bv*[height<=720]+ba[abr<=192]/bv*[height<=720]+ba/b[height<=720]"
    )
    assert _video_format_selector("480", "128", False) == "b[height<=480]"


def test_audio_quality_format_selector():
    assert _audio_format_selector("best") == "bestaudio/best"
    assert _audio_format_selector("192") == (
        "bestaudio[abr<=192]/bestaudio/best"
    )


def test_validate_public_url_rejects_local_and_credentials():
    for url in (
        "http://127.0.0.1/test",
        "http://10.0.0.1/test",
        "http://[::1]/test",
        "https://user:pass@example.com/file",
        "file:///tmp/file.mp4",
    ):
        try:
            validate_public_http_url(url)
        except ValueError:
            pass
        else:
            raise AssertionError(f"URL should be rejected: {url}")


def test_ytdlp_rejects_private_target_before_extractor(tmp_path):
    try:
        _download_with_ytdlp(
            "http://127.0.0.1/private.mp4",
            tmp_path,
            lambda _: None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Private yt-dlp target should be rejected")


def test_content_type_classifier():
    assert _media_kind_from_content_type("image/jpeg; charset=binary") == "images"
    assert _media_kind_from_content_type("video/mp4") == "videos"
    assert _media_kind_from_content_type("audio/mpeg") == "audios"
    assert _media_kind_from_content_type("text/html") is None


def test_download_url_honors_cancel_before_network(tmp_path):
    cancel_event = threading.Event()
    cancel_event.set()

    with pytest.raises(DownloadCancelled):
        download_url(
            "https://example.test/page",
            tmp_path,
            "video",
            lambda _: None,
            cancel_event=cancel_event,
        )


def test_ytdlp_progress_hook_honors_cancel(tmp_path):
    cancel_event = threading.Event()
    cancel_event.set()
    options = _ytdlp_options(
        tmp_path,
        lambda _: None,
        cancel_event=cancel_event,
    )

    with pytest.raises(DownloadCancelled):
        options["progress_hooks"][0]({"status": "downloading"})


def test_download_images_accepts_direct_image_url(monkeypatch, tmp_path):
    calls = []

    def fake_download(url, target_dir, log, index, referer=None):
        calls.append((url, referer))
        path = target_dir / "image.jpg"
        path.write_bytes(b"image")
        return path

    monkeypatch.setattr(downloader, "_download_binary", fake_download)
    count = download_images("https://example.test/photo.jpg", tmp_path, lambda _: None)

    assert count == 1
    assert calls == [("https://example.test/photo.jpg", None)]


def test_all_mode_reports_partial_instead_of_false_success(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "download_video", lambda *args, **kwargs: None)
    monkeypatch.setattr(downloader, "download_images", lambda *args, **kwargs: 0)

    result = download_url(
        "https://example.test/page",
        tmp_path,
        "all",
        lambda _: None,
    )

    assert result.partial is True
    assert result.succeeded == ["video"]
    assert "images" in result.errors


def test_config_load_ignores_unknown_keys_and_normalizes(monkeypatch, tmp_path):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        json.dumps(
            {
                "mode": "invalid",
                "language": "xx",
                "video_quality": "9000",
                "audio_quality": "777",
                "unknown_future_key": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config_module, "APP_DIR", tmp_path)
    monkeypatch.setattr(config_module, "CONFIG_FILE", cfg_file)

    cfg = AppConfig.load()

    assert cfg.mode == "all"
    assert cfg.language == "it"
    assert cfg.video_quality == "best"
    assert cfg.audio_quality == "best"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_extension_origin_helper():
    assert is_extension_origin("chrome-extension://abc")
    assert is_extension_origin("edge-extension://abc")
    assert not is_extension_origin("https://evil.example")
    assert not is_extension_origin("")


def test_local_server_rejects_web_origin_and_requires_token(monkeypatch):
    monkeypatch.setattr(server_module, "validate_public_http_url", lambda url: url)
    monkeypatch.setattr(
        server_module,
        "download_url",
        lambda *args, **kwargs: DownloadResult(succeeded=["video"]),
    )

    cfg = AppConfig(port=_free_port())
    logs = []
    server = LocalServer(cfg, logs.append)
    server.start()
    base = f"http://127.0.0.1:{cfg.port}"

    try:
        evil = requests.post(
            f"{base}/download",
            headers={
                "Origin": "https://evil.example",
                "Content-Type": "application/json",
                "X-MediaGrab-Token": "wrong",
            },
            json={"url": "https://example.com/video"},
            timeout=3,
        )
        assert evil.status_code == 403

        health = requests.get(
            f"{base}/health",
            headers={
                "Origin": "chrome-extension://test",
                "X-MediaGrab-Client": "extension",
            },
            timeout=3,
        )
        assert health.status_code == 200
        token = health.json()["session_token"]
        assert token

        missing_token = requests.post(
            f"{base}/download",
            headers={
                "Origin": "chrome-extension://test",
                "Content-Type": "application/json",
            },
            json={"url": "https://example.com/video"},
            timeout=3,
        )
        assert missing_token.status_code == 403

        accepted = requests.post(
            f"{base}/download",
            headers={
                "Origin": "chrome-extension://test",
                "Content-Type": "application/json",
                "X-MediaGrab-Token": token,
            },
            json={"url": "https://example.com/video", "candidates": []},
            timeout=3,
        )
        assert accepted.status_code == 202

        time.sleep(0.05)
    finally:
        server.stop()
