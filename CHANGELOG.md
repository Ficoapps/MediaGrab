# Changelog

## 0.2.0

- Motore di download multi-strategia: yt-dlp, HTML statico e sorgenti rilevate dal browser.
- Rilevamento di MP4, WebM, HLS (`.m3u8`) e DASH (`.mpd`) quando esposti dalla pagina.
- Estensione Chrome/Edge aggiornata: analizza DOM e Performance API della scheda attiva.
- Supporto migliorato per immagini lazy-loaded e sorgenti dinamiche.
- Messaggi di errore più chiari quando una pagina non espone media scaricabili.
- Il server locale accetta un elenco limitato e validato di sorgenti individuate dal browser.
- Workflow Windows aggiornato con test automatici prima del build.
- Nessun bypass di DRM, paywall o controlli di accesso.

## 0.1.0

- Prima versione MVP.
- Download video tramite yt-dlp.
- Download immagini dall'HTML.
- Connettore locale per estensione Chrome/Edge.
