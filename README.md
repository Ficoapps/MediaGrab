# MediaGrab 0.4.3

## Italiano

MediaGrab è un'app desktop per Windows con estensione Chrome/Edge che permette di rilevare e scaricare **video, audio e immagini pubblicamente accessibili** dalle pagine web.

### Novità 0.4.3

- Aggiunto il pulsante **Annulla** per interrompere in modo cooperativo i download avviati dall'app.
- Il controllo di annullamento viene verificato durante download HTTP, analisi HTML e download yt-dlp.
- Le immagini vengono scaricate con un massimo di **4 worker contemporanei** per velocizzare le pagine con molte immagini senza creare concorrenza incontrollata.
- Le sorgenti immagini senza estensione vengono riconosciute anche tramite **Content-Type**.
- I file temporanei `.part` vengono riservati in modo atomico per evitare collisioni durante download immagini paralleli.
- Le sorgenti immagini vengono limitate a un massimo di **250 elementi per pagina** per contenere uso di memoria e rete.

### Novità 0.4.2

- Anche gli URL consegnati a **yt-dlp** vengono validati prima del download, compresi quelli scoperti tramite il fallback HTML.
- Il listener HTTP locale non crea più un thread per ogni richiesta; i download pesanti continuano a usare il pool limitato.

### Novità 0.4.1

- Connettore browser protetto con **token casuale di sessione**.
- Rifiuto delle Origin web non autorizzate e delle richieste non JSON.
- Coda browser limitata a **3 download attivi** e **8 richieste complessive in coda/esecuzione**.
- Blocco di localhost, reti private e link-local per i download avviati dall'estensione.
- Corretto lo stato della modalità **Tutto**: ora distingue successo completo, parziale ed errore.
- Supporto agli **URL immagine diretti**.
- Le immagini vengono prima salvate come file `.part`, così un errore non lascia un file apparentemente completo.
- Limite di 10 MB per l'HTML analizzato e 200 MB per una singola immagine.
- Riutilizzo dell'analisi HTML nella modalità Tutto quando serve il fallback.
- Log dell'interfaccia limitato alle ultime 5.000 righe.
- Configurazione più robusta e salvataggio atomico.
- Dipendenze principali bloccate a versioni precise; Pillow rimosso perché non utilizzato.
- La Release include sia `MediaGrab.exe` sia `MediaGrab-Extension.zip`.

### Qualità video e audio

**Video:** Migliore disponibile, 2160p, 1440p, 1080p, 720p, 480p o 360p.

**Audio:** Migliore disponibile, 320, 256, 192, 128 o 96 kbps.

Per i video MediaGrab sceglie il miglior flusso disponibile entro la risoluzione indicata. In modalità **Solo audio**, se FFmpeg è disponibile, il bitrate selezionato viene usato per l'MP3 finale.

### Modalità disponibili

- Tutto (video + immagini)
- Solo video
- Solo audio
- Solo immagini

### Installazione

1. Scarica `MediaGrab.exe` dalla Release più recente.
2. Scarica anche `MediaGrab-Extension.zip` dalla **stessa Release**.
3. Avvia `MediaGrab.exe`.
4. Estrai `MediaGrab-Extension.zip`.
5. Apri `chrome://extensions` oppure `edge://extensions`.
6. Attiva **Modalità sviluppatore**.
7. Seleziona **Carica estensione non pacchettizzata** e indica la cartella estratta.

**App ed estensione 0.4.3 vanno usate insieme**, perché il collegamento locale usa il nuovo token di sessione.

### Annullamento download

Il pulsante **Annulla** interrompe in modo cooperativo il download corrente e ferma la coda successiva. Durante alcune fasi finali gestite da FFmpeg, come merge o conversione, l'interruzione può non essere istantanea.

### Download multiplo

Nel campo URL inserisci uno o più indirizzi, uno per riga. MediaGrab li elabora in sequenza e continua con il successivo anche se un download fallisce.

### Come funziona

1. **yt-dlp** per i siti supportati direttamente.
2. **Analisi HTML** per video, audio, immagini, Open Graph e URL media esposti nel sorgente.
3. **Estensione Chrome/Edge** per media caricati dinamicamente nel browser.
4. **HLS/DASH** quando la pagina espone manifest `.m3u8` o `.mpd`.

MediaGrab non rimuove DRM, non aggira paywall e non forza accesso a contenuti ai quali l'utente non ha accesso.

---

## English

MediaGrab is a Windows desktop app with a Chrome/Edge extension that can detect and download publicly accessible **video, audio and images** from web pages.

### What's new in 0.4.3

- Added a **Cancel** button for cooperative cancellation of downloads started from the desktop app.
- Cancellation is checked during HTTP downloads, HTML analysis and yt-dlp downloads.
- Images are downloaded with at most **4 concurrent workers** to improve performance without unbounded concurrency.
- Extensionless image sources can also be recognized through the HTTP **Content-Type**.
- Temporary `.part` files are reserved atomically to avoid filename races during parallel image downloads.
- Image sources are capped at **250 items per page** to bound memory and network usage.

### What's new in 0.4.2

- URLs passed to **yt-dlp** are now validated before extraction, including URLs discovered through HTML fallback detection.
- The local HTTP listener no longer creates one thread per request; heavy downloads still run in the bounded worker pool.

### What's new in 0.4.1

- The browser connector now uses a **random session token**.
- Unauthorized web origins and non-JSON download requests are rejected.
- Browser-triggered downloads use a bounded queue with **3 active workers** and **8 total queued/running jobs**.
- Localhost, private and link-local destinations are blocked for extension-triggered downloads.
- **All** mode now correctly reports complete, partial and failed downloads.
- Direct image URLs are supported.
- Images are written to temporary `.part` files before final rename.
- HTML analysis is limited to 10 MB and a single image download to 200 MB.
- HTML detection results are reused in All mode when fallback detection is needed.
- The activity log is capped at the latest 5,000 lines.
- Configuration loading is more robust and saves are atomic.
- Direct Python dependencies are pinned; unused Pillow was removed.
- Releases include both `MediaGrab.exe` and `MediaGrab-Extension.zip`.

### Video and audio quality

**Video:** Best available, 2160p, 1440p, 1080p, 720p, 480p or 360p.

**Audio:** Best available, 320, 256, 192, 128 or 96 kbps.

For video, MediaGrab chooses the best stream available within the selected resolution. In **Audio only** mode, if FFmpeg is available, the selected bitrate is used for the final MP3.

### Available modes

- All (video + images)
- Video only
- Audio only
- Images only

### Installation

1. Download `MediaGrab.exe` from the latest Release.
2. Download `MediaGrab-Extension.zip` from the **same Release**.
3. Start `MediaGrab.exe`.
4. Extract `MediaGrab-Extension.zip`.
5. Open `chrome://extensions` or `edge://extensions`.
6. Enable **Developer mode**.
7. Choose **Load unpacked** and select the extracted extension folder.

**App and extension 0.4.3 must be used together** because the local connector now uses a session token.

### Cancelling downloads

The **Cancel** button cooperatively stops the current desktop-app download and prevents later queued URLs from starting. During final FFmpeg merge or conversion steps, cancellation may not be instantaneous.

### Multiple downloads

Paste one or more URLs, one per line. MediaGrab processes them sequentially and continues with the next URL if one download fails.

### How it works

1. **yt-dlp** for directly supported websites.
2. **HTML analysis** for video, audio, images, Open Graph metadata and exposed media URLs.
3. **Chrome/Edge extension** for media loaded dynamically in the browser.
4. **HLS/DASH** when accessible `.m3u8` or `.mpd` manifests are exposed.

MediaGrab does not remove DRM, bypass paywalls, or force access to content the user cannot legitimately access.

---

## Development

- Python 3.12 is used for the official Windows build.
- FFmpeg is recommended for audio conversion and merging separate audio/video streams.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python main.py
```

## License

MIT.
