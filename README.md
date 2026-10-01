# MediaGrab 0.4.1

MediaGrab è un'app desktop per Windows con estensione Chrome/Edge per rilevare e scaricare **video, audio e immagini pubblicamente accessibili** dalle pagine web.

## Funzioni

- Video con qualità selezionabile: migliore disponibile, 2160p, 1440p, 1080p, 720p, 480p o 360p.
- Audio con qualità selezionabile: migliore disponibile, 320, 256, 192, 128 o 96 kbps.
- Modalità: **Tutto (video + immagini)**, **Solo video**, **Solo audio**, **Solo immagini**.
- Più URL in coda, uno per riga.
- Interfaccia Italiano / English.
- Rilevamento tramite yt-dlp, HTML statico ed estensione Chrome/Edge.
- Supporto per sorgenti HLS/DASH esposte dalla pagina.

## Novità 0.4.1

La versione 0.4.1 rende più robusto il connettore locale tra browser e applicazione:

- token casuale di sessione;
- rifiuto delle Origin web non autorizzate;
- coda limitata per evitare la creazione incontrollata di thread;
- blocco delle destinazioni localhost/private per richieste avviate dall'estensione;
- segnalazione corretta dei download parziali;
- supporto agli URL immagine diretti;
- file temporanei `.part` per evitare di lasciare immagini incomplete;
- limiti alla dimensione dell'HTML e delle immagini analizzate/scaricate;
- configurazione salvata in modo atomico;
- dipendenze principali bloccate a versioni precise.

## Installazione

1. Scarica `MediaGrab.exe` dalla Release più recente.
2. Scarica anche `MediaGrab-Extension.zip` dalla **stessa Release**.
3. Avvia `MediaGrab.exe`.
4. Estrai `MediaGrab-Extension.zip`.
5. In Chrome apri `chrome://extensions`, oppure in Edge `edge://extensions`.
6. Attiva **Modalità sviluppatore**.
7. Seleziona **Carica estensione non pacchettizzata** e indica la cartella estratta.

L'estensione 0.4.1 e l'app 0.4.1 vanno usate insieme perché il connettore locale usa un token di sessione.

## Qualità audio

In modalità **Solo audio**, se FFmpeg è disponibile, MediaGrab converte in MP3 usando il bitrate selezionato. Senza FFmpeg mantiene il miglior formato audio sorgente compatibile con il limite scelto.

## Sicurezza e limiti

MediaGrab non rimuove DRM, non aggira paywall e non forza accesso a contenuti non disponibili all'utente. Il connettore browser ascolta esclusivamente su `127.0.0.1`.

## Development

- Python 3.12 usato dalla build Windows ufficiale.
- FFmpeg consigliato per conversione audio e unione di flussi audio/video separati.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
python main.py
```

## License

MIT.
