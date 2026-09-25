from mediagrab.downloader import (
    _safe_name,
    extract_media_from_html,
    normalize_batch_urls,
)


def test_safe_name_removes_windows_forbidden_chars():
    assert _safe_name('a:b*c?.mp4') == 'a_b_c_.mp4'


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
