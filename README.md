# MediaGrab 0.2

MediaGrab è un'app desktop per Windows con estensione Chrome/Edge che prova a rilevare e scaricare foto e video pubblicamente accessibili da una pagina web.

## Come funziona

MediaGrab usa più strategie in cascata:

1. **yt-dlp** per i siti supportati direttamente.
2. **Analisi HTML** per `<video>`, `<source>`, immagini, metadati Open Graph e URL media presenti nel codice sorgente.
3. **Estensione browser** per rilevare media caricati dinamicamente nella scheda aperta, inclusi URL osservabili tramite DOM e Performance API.
4. **HLS/DASH** quando la pagina espone manifest `.m3u8` o `.mpd` accessibili.

L'app non rimuove DRM, non aggira paywall e non forza contenuti per i quali l'utente non dispone dell'accesso.

## Requisiti per sviluppo

- Python 3.10+
- Windows 10/11 consigliato
- FFmpeg consigliato per flussi con audio e video separati

## Avvio da sorgente

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

## Estensione Chrome / Edge

1. Avvia MediaGrab e lascia attivo **collegamento con estensione Chrome/Edge**.
2. Apri `chrome://extensions` oppure `edge://extensions`.
3. Attiva **Modalità sviluppatore**.
4. Scegli **Carica estensione non pacchettizzata**.
5. Seleziona la cartella `extension` del progetto.
6. Apri una pagina con media visibile e premi l'icona di MediaGrab.

L'estensione invia all'app l'URL della pagina e le sorgenti media che riesce a osservare nella scheda corrente.

## Build Windows

Il workflow GitHub Actions `.github/workflows/build-windows.yml` esegue i test e crea `MediaGrab.exe` tramite PyInstaller.

## Limiti

Nessun downloader può garantire compatibilità letterale con ogni sito. Pagine con DRM, cifratura, CAPTCHA, sessioni non esportabili o player che nascondono completamente le sorgenti possono non essere scaricabili. MediaGrab tenta solo sorgenti accessibili senza aggirare protezioni.

## Licenza

MIT.
