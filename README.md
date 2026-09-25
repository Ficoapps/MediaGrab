# MediaGrab

MediaGrab è un'app desktop per Windows che scarica **video e immagini** da una pagina web e può ricevere l'URL della scheda corrente da una piccola estensione Chrome/Edge.

> **Uso responsabile:** scarica solo contenuti che hai diritto di salvare. Il progetto non è progettato per aggirare DRM, paywall, autenticazioni, protezioni anticopia o altre restrizioni di accesso.

## Funzioni

- Interfaccia grafica semplice.
- Modalità `Solo video`, `Solo immagini`, `Tutto`.
- Video gestiti tramite `yt-dlp`.
- Immagini raccolte dagli elementi HTML `img`, `srcset`, `og:image` e `twitter:image`.
- Estensione Chrome/Edge: un clic sull'icona invia la pagina corrente a MediaGrab.
- Server locale solo su `127.0.0.1:8765`.
- Build Windows `.exe` tramite PyInstaller.
- Workflow GitHub Actions per produrre automaticamente l'EXE quando crei un tag `v*`.

## Requisiti

- Windows 10/11.
- Python 3.10 o superiore.
- Per alcuni video, `ffmpeg` è necessario per unire traccia video e audio.

## Installazione per sviluppatori

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Estensione Chrome / Edge

1. Avvia MediaGrab e lascia attiva la voce **collegamento con estensione Chrome/Edge**.
2. Apri `chrome://extensions` oppure `edge://extensions`.
3. Attiva **Modalità sviluppatore**.
4. Scegli **Carica estensione non pacchettizzata**.
5. Seleziona la cartella `extension` del progetto.
6. Fissa l'estensione alla barra degli strumenti.
7. Apri una pagina web e premi l'icona MediaGrab.

L'app userà la modalità selezionata nell'interfaccia (`Video`, `Immagini` oppure `Tutto`).

## Creare l'EXE su Windows

```powershell
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean --onefile --windowed --name MediaGrab main.py
```

Il file viene generato in:

```text
dist/MediaGrab.exe
```

## Pubblicare su GitHub

```powershell
git init
git add .
git commit -m "Initial MediaGrab MVP"
git branch -M main
git remote add origin https://github.com/TUO-USERNAME/MediaGrab.git
git push -u origin main
```

Per far generare l'EXE a GitHub Actions:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## Struttura

```text
MediaGrab/
├─ main.py
├─ mediagrab/
│  ├─ config.py
│  ├─ downloader.py
│  ├─ gui.py
│  └─ server.py
├─ extension/
│  ├─ manifest.json
│  └─ background.js
├─ tests/
├─ .github/workflows/build-windows.yml
├─ requirements.txt
├─ requirements-dev.txt
├─ LICENSE
└─ README.md
```

## Limiti dell'MVP

- Le immagini caricate esclusivamente via JavaScript dopo lo scrolling potrebbero non essere rilevate.
- Alcuni siti richiedono cookie/sessioni utente; questa versione non importa automaticamente i cookie del browser.
- I contenuti protetti da DRM non sono supportati.
- Alcuni siti cambiano spesso struttura e possono richiedere adattamenti.

## Roadmap

- Anteprima dei media prima del download.
- Selettore qualità video e formato.
- Download di una singola immagine con menu contestuale.
- Coda download con percentuale e velocità.
- Import opzionale dei cookie, solo quando legittimamente necessario e scelto dall'utente.
- Installer Windows firmabile.
- Aggiornamenti automatici dell'app.
