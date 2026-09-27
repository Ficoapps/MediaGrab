# MediaGrab 0.4

## Italiano

MediaGrab è un'app desktop per Windows con estensione Chrome/Edge che permette di rilevare e scaricare **video, audio e immagini** pubblicamente accessibili dalle pagine web.

### Novità 0.4

- **Qualità video selezionabile**: Migliore disponibile, 2160p, 1440p, 1080p, 720p, 480p o 360p.
- **Qualità audio selezionabile**: Migliore disponibile, 320, 256, 192, 128 o 96 kbps.
- Per i video MediaGrab sceglie il miglior flusso disponibile entro la risoluzione indicata.
- In modalità **Solo audio**, con FFmpeg installato, il bitrate scelto viene usato per l'MP3 finale.
- Le preferenze di qualità vengono salvate e usate anche dai download avviati tramite estensione Chrome/Edge.

### Funzioni già presenti

- **Solo audio**: scarica la migliore traccia audio disponibile.
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

MediaGrab is a Windows desktop app with a Chrome/Edge extension that can detect and download publicly accessible **video, audio and images** from web pages.

### What's new in 0.4

- **Selectable video quality**: Best available, 2160p, 1440p, 1080p, 720p, 480p or 360p.
- **Selectable audio quality**: Best available, 320, 256, 192, 128 or 96 kbps.
- For video, MediaGrab selects the best stream available within the chosen resolution.
- In **Audio only** mode, when FFmpeg is installed, the selected bitrate is used for the final MP3.
- Quality preferences are saved and also used for downloads started from the Chrome/Edge extension.

### Existing features

- **Audio only** mode.
- MP3 conversion when FFmpeg is available.
- **Multiple downloads**: paste multiple URLs, one per line.
- **Bilingual interface**: Italiano / English.
- Browser connector detection for common video, audio and image formats.

### Available modes

- All (video + images)
- Video only
- Audio only
- Images only

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
