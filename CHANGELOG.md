# Changelog

## 0.3.0

- Added **audio-only** download mode.
- MP3 conversion when FFmpeg is available; otherwise MediaGrab keeps the best available audio format.
- Added **multiple URL queue**: one URL per line, processed sequentially.
- Added **Italian / English language selector** with persistent language preference.
- Browser extension now detects common audio formats and audio DOM elements.
- Added audio URL extraction from HTML and Open Graph metadata.
- Updated tests and Windows build artifact to 0.3.0.
- No DRM, paywall, or access-control bypass.

## 0.2.0

- Multi-strategy download engine: yt-dlp, static HTML and browser-detected sources.
- Detection of MP4, WebM, HLS (`.m3u8`) and DASH (`.mpd`) when exposed by the page.
- Chrome/Edge extension scans DOM and Performance API.
- Improved lazy-loaded image and dynamic-source support.
- Clearer errors when media cannot be detected.
- Windows workflow runs tests before building.
- No DRM, paywall, or access-control bypass.

## 0.1.0

- First MVP.
- Video download through yt-dlp.
- Image download from HTML.
- Local connector for Chrome/Edge extension.
