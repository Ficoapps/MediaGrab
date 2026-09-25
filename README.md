# MediaGrab 0.3

## Italiano

MediaGrab è un'app desktop per Windows con estensione Chrome/Edge che prova a rilevare e scaricare media pubblicamente accessibili dalle pagine web.

### Novità 0.3

- **Solo audio**: nuova modalità per scaricare la migliore traccia audio disponibile.
- Se FFmpeg è disponibile, l'audio viene convertito in **MP3**; altrimenti viene mantenuto il miglior formato audio originale disponibile.
- **Download multiplo**: puoi incollare più URL, uno per riga, e MediaGrab li elabora in sequenza.
- **Interfaccia bilingue**: selettore **Italiano / English** direttamente nell'app.
- Il browser connector riconosce anche sorgenti audio come MP3, M4A, AAC, OGG, Opus, WAV e FLAC.

### Modalità disponibili

- Tutto (video + immagini)
- Solo video
- Solo audio
- Solo immagini

### Download multiplo

Nel campo URL inserisci uno o più indirizzi, uno per riga. MediaGrab li mette in coda e continua con il successivo anche se uno dei download fallisce.

### Come funziona

1. **yt-dlp** per i siti supportati direttamente.
2. **Analisi HTML** per video, audio, immagini, metadati Open Graph e URL media presenti nel sorgente.
3. **Estensione Chrome/Edge** per media caricati dinamicamente nel browser.
4. **HLS/DASH** quando la pagina espone manifest `.m3u8` o `.mpd`.

MediaGrab non rimuove DRM, non aggira paywall e non forza contenuti ai quali l'utente non ha accesso.

---

## English

MediaGrab is a Windows desktop app with a Chrome/Edge extension that attempts to detect and download publicly accessible media from web pages.

### What's new in 0.3

- **Audio only**: download the best available audio track.
- If FFmpeg is available, audio is converted to **MP3**; otherwise MediaGrab keeps the best original audio format available.
- **Multiple downloads**: paste multiple URLs, one per line, and MediaGrab processes them sequentially.
- **Bilingual interface**: switch between **Italiano / English** directly in the app.
- The browser connector also detects audio sources such as MP3, M4A, AAC, OGG, Opus, WAV and FLAC.

### Available modes

- All (video + images)
- Video only
- Audio only
- Images only

### Multiple downloads

Paste one or more addresses in the URL field, one per line. MediaGrab queues them and continues with the next URL even if one download fails.

### How it works

1. **yt-dlp** for directly supported websites.
2. **HTML analysis** for video, audio, images, Open Graph metadata and media URLs exposed in page source.
3. **Chrome/Edge extension** for media loaded dynamically in the browser.
4. **HLS/DASH** when accessible `.m3u8` or `.mpd` manifests are exposed.

MediaGrab does not remove DRM, bypass paywalls, or force access to content the user cannot legitimately access.

---

## Development

- Python 3.10+
- Windows 10/11 recommended
- FFmpeg recommended for audio extraction/conversion and separate audio/video streams

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Chrome / Edge extension

1. Start MediaGrab and keep the browser connection enabled.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked**.
5. Select the `extension` folder.
6. Open a page containing media and click the MediaGrab extension icon.

## License

MIT.
