# Changelog

## 0.4.1

- Protected the local browser connector with a random session token.
- Rejects unauthorized web origins and non-JSON download requests.
- Added a bounded download queue with at most 3 active workers and 8 pending jobs.
- Added validation against localhost/private/link-local destinations for browser-triggered requests.
- Fixed `all` mode falsely reporting complete success when only video or images succeeded.
- Added direct image URL support.
- Image downloads now use `.part` temporary files and remove incomplete files after errors.
- Limited HTML analysis to 10 MB and individual image downloads to 200 MB.
- Reuses HTML media analysis inside `all` mode instead of fetching the same page twice when fallback detection is needed.
- Limited the GUI activity log to the latest 5,000 lines.
- Centralized application version and shared quality constants.
- Hardened configuration loading and made configuration saves atomic.
- Pinned direct Python dependencies and removed unused Pillow dependency.
- GitHub Actions now uses read-only permissions for builds and write access only for the release job.
- Release now includes the matching Chrome/Edge extension ZIP.

## 0.4.0

- Added selectable **video quality**: Best, 2160p, 1440p, 1080p, 720p, 480p and 360p.
- Added selectable **audio quality**: Best, 320, 256, 192, 128 and 96 kbps.
- Quality preferences are persisted in the app configuration.
- Browser-extension downloads inherit the selected quality settings.
- Audio-only MP3 conversion uses the selected bitrate when FFmpeg is available.
- Updated tests and Windows release build.
- No DRM, paywall, or access-control bypass.

## 0.3.0

- Added **audio-only** download mode.
- MP3 conversion when FFmpeg is available; otherwise MediaGrab keeps the best available audio format.
- Added **multiple URL queue**: one URL per line, processed sequentially.
- Added **Italian / English language selector** with persistent language preference.
- Browser extension now detects common audio formats and audio DOM elements.
- Added audio URL extraction from HTML and Open Graph metadata.
- Updated tests and Windows build artifact to 0.3.0.
- No DRM, paywall, or access-control bypass.
