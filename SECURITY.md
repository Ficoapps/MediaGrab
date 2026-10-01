# Security policy

MediaGrab espone il connettore soltanto su `127.0.0.1`.

Dalla versione 0.4.1 il connettore:

- usa un token casuale di sessione tra estensione e app desktop;
- rifiuta Origin web non autorizzate;
- accetta download soltanto tramite JSON;
- limita il numero di download contemporanei e in coda;
- rifiuta URL che puntano a localhost, reti private, link-local o altri indirizzi non pubblici quando arrivano dal connettore browser.

Non configurare MediaGrab per ascoltare su interfacce di rete pubbliche.
Non inserire token, password o cookie personali nel repository.

Per vulnerabilità, usare GitHub Security Advisories invece di pubblicare credenziali o dettagli sensibili in una issue.
