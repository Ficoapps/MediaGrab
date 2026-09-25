from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import AppConfig
from .downloader import download_url, normalize_batch_urls
from .server import LocalServer

TEXTS = {
    "it": {
        "title": "MediaGrab 0.3",
        "subtitle": "Scarica video, solo audio, immagini o più URL in un'unica coda.",
        "urls": "URL (uno per riga)",
        "urls_help": "Puoi incollare più indirizzi: MediaGrab li elaborerà uno dopo l'altro.",
        "folder": "Cartella",
        "browse": "Sfoglia…",
        "mode": "Modalità",
        "language": "Lingua",
        "browser": "Attiva collegamento con estensione Chrome/Edge",
        "download": "Scarica",
        "clear": "Svuota URL",
        "open_folder": "Apri cartella",
        "activity": "Attività",
        "ready": "Pronto",
        "warning_no_urls": "Inserisci almeno un URL http:// o https://, uno per riga.",
        "processed": "{done}/{total} elaborati",
        "errors": " · {count} errori",
        "completed": "Completato: {ok}/{total}",
        "finished_partial": "Terminato: {ok}/{total} riusciti",
        "item_completed": "[{index}/{total}] Completato.",
        "item_error": "[{index}/{total}] Errore: {error}",
        "server_error": "Impossibile avviare il connettore browser: {error}",
        "modes": {
            "all": "Tutto (video + immagini)",
            "video": "Solo video",
            "audio": "Solo audio",
            "images": "Solo immagini",
        },
    },
    "en": {
        "title": "MediaGrab 0.3",
        "subtitle": "Download video, audio only, images, or multiple URLs in one queue.",
        "urls": "URLs (one per line)",
        "urls_help": "Paste multiple addresses and MediaGrab will process them one after another.",
        "folder": "Folder",
        "browse": "Browse…",
        "mode": "Mode",
        "language": "Language",
        "browser": "Enable Chrome/Edge extension connection",
        "download": "Download",
        "clear": "Clear URLs",
        "open_folder": "Open folder",
        "activity": "Activity",
        "ready": "Ready",
        "warning_no_urls": "Enter at least one valid http:// or https:// URL, one per line.",
        "processed": "{done}/{total} processed",
        "errors": " · {count} errors",
        "completed": "Completed: {ok}/{total}",
        "finished_partial": "Finished: {ok}/{total} succeeded",
        "item_completed": "[{index}/{total}] Completed.",
        "item_error": "[{index}/{total}] Error: {error}",
        "server_error": "Could not start browser connector: {error}",
        "modes": {
            "all": "All (video + images)",
            "video": "Video only",
            "audio": "Audio only",
            "images": "Images only",
        },
    },
}

LANGUAGE_LABELS = {
    "Italiano": "it",
    "English": "en",
}
LANGUAGE_LABELS_REVERSE = {v: k for k, v in LANGUAGE_LABELS.items()}


class MediaGrabApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.config_data = AppConfig.load()
        if self.config_data.language not in TEXTS:
            self.config_data.language = "it"

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.server = LocalServer(self.config_data, self.log)

        self.output_var = tk.StringVar(value=self.config_data.output_dir)
        self.mode_var = tk.StringVar()
        self.language_var = tk.StringVar(
            value=LANGUAGE_LABELS_REVERSE.get(
                self.config_data.language,
                "Italiano",
            )
        )
        self.server_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar()

        self.geometry("840x700")
        self.minsize(740, 580)

        self._build_ui()
        self._apply_language()
        self.after(100, self._drain_logs)
        self.after(250, self._start_server)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def lang(self) -> str:
        return self.config_data.language if self.config_data.language in TEXTS else "it"

    def t(self, key: str) -> str:
        return TEXTS[self.lang][key]

    def _mode_labels(self) -> dict[str, str]:
        return TEXTS[self.lang]["modes"]

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        self.title_label = ttk.Label(
            root,
            font=("Segoe UI", 20, "bold"),
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = ttk.Label(root)
        self.subtitle_label.pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(root)
        top.pack(fill="x", pady=(0, 8))
        top.columnconfigure(1, weight=1)

        self.language_label = ttk.Label(top)
        self.language_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
        )

        self.language_combo = ttk.Combobox(
            top,
            textvariable=self.language_var,
            values=list(LANGUAGE_LABELS),
            state="readonly",
            width=14,
        )
        self.language_combo.grid(row=0, column=1, sticky="w")
        self.language_combo.bind(
            "<<ComboboxSelected>>",
            self._language_changed,
        )

        self.urls_label = ttk.Label(root)
        self.urls_label.pack(anchor="w")

        self.url_text = tk.Text(root, height=6, wrap="word")
        self.url_text.pack(fill="x", pady=(4, 4))

        self.urls_help_label = ttk.Label(root)
        self.urls_help_label.pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(root)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        self.folder_label = ttk.Label(form)
        self.folder_label.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=6,
        )

        out_row = ttk.Frame(form)
        out_row.grid(row=0, column=1, sticky="ew", pady=6)
        out_row.columnconfigure(0, weight=1)

        ttk.Entry(
            out_row,
            textvariable=self.output_var,
        ).grid(row=0, column=0, sticky="ew")

        self.browse_btn = ttk.Button(
            out_row,
            command=self._choose_folder,
        )
        self.browse_btn.grid(row=0, column=1, padx=(8, 0))

        self.mode_label = ttk.Label(form)
        self.mode_label.grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=6,
        )

        self.mode_combo = ttk.Combobox(
            form,
            textvariable=self.mode_var,
            state="readonly",
        )
        self.mode_combo.grid(
            row=1,
            column=1,
            sticky="ew",
            pady=6,
        )
        self.mode_combo.bind(
            "<<ComboboxSelected>>",
            lambda _: self._save_config(),
        )

        self.server_check = ttk.Checkbutton(
            form,
            variable=self.server_var,
            command=self._toggle_server,
        )
        self.server_check.grid(
            row=2,
            column=1,
            sticky="w",
            pady=8,
        )

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(10, 12))

        self.download_btn = ttk.Button(
            actions,
            command=self._download_clicked,
        )
        self.download_btn.pack(side="left")

        self.clear_btn = ttk.Button(
            actions,
            command=lambda: self.url_text.delete("1.0", "end"),
        )
        self.clear_btn.pack(side="left", padx=(8, 0))

        self.open_folder_btn = ttk.Button(
            actions,
            command=self._open_folder,
        )
        self.open_folder_btn.pack(side="left", padx=8)

        ttk.Label(
            actions,
            textvariable=self.status_var,
        ).pack(side="right")

        ttk.Separator(root).pack(
            fill="x",
            pady=(0, 8),
        )

        self.activity_label = ttk.Label(
            root,
            font=("Segoe UI", 10, "bold"),
        )
        self.activity_label.pack(anchor="w")

        self.log_text = tk.Text(
            root,
            height=16,
            wrap="word",
            state="disabled",
        )
        self.log_text.pack(
            fill="both",
            expand=True,
            pady=(6, 0),
        )

    def _apply_language(self) -> None:
        self.title(self.t("title"))
        self.title_label.configure(text=self.t("title"))
        self.subtitle_label.configure(text=self.t("subtitle"))
        self.urls_label.configure(text=self.t("urls"))
        self.urls_help_label.configure(text=self.t("urls_help"))
        self.folder_label.configure(text=self.t("folder"))
        self.browse_btn.configure(text=self.t("browse"))
        self.mode_label.configure(text=self.t("mode"))
        self.language_label.configure(text=self.t("language"))
        self.server_check.configure(text=self.t("browser"))
        self.download_btn.configure(text=self.t("download"))
        self.clear_btn.configure(text=self.t("clear"))
        self.open_folder_btn.configure(text=self.t("open_folder"))
        self.activity_label.configure(text=self.t("activity"))

        mode_labels = self._mode_labels()
        self.mode_combo.configure(values=list(mode_labels.values()))
        self.mode_var.set(
            mode_labels.get(
                self.config_data.mode,
                mode_labels["all"],
            )
        )

        if not self.status_var.get():
            self.status_var.set(self.t("ready"))
        elif self.status_var.get() in {
            TEXTS["it"]["ready"],
            TEXTS["en"]["ready"],
        }:
            self.status_var.set(self.t("ready"))

    def _language_changed(self, _event=None) -> None:
        code = LANGUAGE_LABELS.get(self.language_var.get(), "it")
        self.config_data.language = code
        self._apply_language()
        self._save_config()

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(
            initialdir=self.output_var.get()
        )
        if selected:
            self.output_var.set(selected)
            self._save_config()

    def _selected_mode_code(self) -> str:
        current = self.mode_var.get()
        for code, label in self._mode_labels().items():
            if label == current:
                return code
        return "all"

    def _save_config(self) -> None:
        self.config_data.output_dir = self.output_var.get().strip()
        self.config_data.mode = self._selected_mode_code()
        self.config_data.language = LANGUAGE_LABELS.get(
            self.language_var.get(),
            self.lang,
        )
        self.config_data.save()

    def _read_urls(self) -> list[str]:
        values = self.url_text.get("1.0", "end").splitlines()
        return normalize_batch_urls(values)

    def _download_clicked(self) -> None:
        urls = self._read_urls()
        if not urls:
            messagebox.showwarning(
                "MediaGrab",
                self.t("warning_no_urls"),
            )
            return

        self._save_config()
        language_at_start = self.lang
        texts = TEXTS[language_at_start]

        self.download_btn.configure(state="disabled")
        self.status_var.set(
            texts["processed"].format(
                done=0,
                total=len(urls),
            )
        )

        def run() -> None:
            failed = 0

            for index, url in enumerate(urls, start=1):
                self.log("")
                self.log("=" * 64)
                self.log(f"[{index}/{len(urls)}] {url}")
                self.log("=" * 64)

                try:
                    download_url(
                        url,
                        self.config_data.output_dir,
                        self.config_data.mode,
                        self.log,
                    )
                    self.log(
                        texts["item_completed"].format(
                            index=index,
                            total=len(urls),
                        )
                    )
                except Exception as exc:
                    failed += 1
                    self.log(
                        texts["item_error"].format(
                            index=index,
                            total=len(urls),
                            error=exc,
                        )
                    )

                status = texts["processed"].format(
                    done=index,
                    total=len(urls),
                )
                if failed:
                    status += texts["errors"].format(count=failed)

                self.after(
                    0,
                    lambda value=status: self.status_var.set(value),
                )

            ok = len(urls) - failed
            if failed:
                final = texts["finished_partial"].format(
                    ok=ok,
                    total=len(urls),
                )
            else:
                final = texts["completed"].format(
                    ok=ok,
                    total=len(urls),
                )

            self.log(final)
            self.after(
                0,
                lambda value=final: self.status_var.set(value),
            )
            self.after(
                0,
                lambda: self.download_btn.configure(state="normal"),
            )

        threading.Thread(
            target=run,
            daemon=True,
        ).start()

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_logs(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break

            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.after(100, self._drain_logs)

    def _start_server(self) -> None:
        if self.server_var.get():
            try:
                self.server.start()
            except OSError as exc:
                self.log(
                    self.t("server_error").format(error=exc)
                )
                self.server_var.set(False)

    def _toggle_server(self) -> None:
        if self.server_var.get():
            self._start_server()
        else:
            self.server.stop()

    def _open_folder(self) -> None:
        folder = Path(self.output_var.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif os.name == "posix":
            subprocess.Popen(["xdg-open", str(folder)])

    def _on_close(self) -> None:
        self._save_config()
        self.server.stop()
        self.destroy()


def main() -> None:
    app = MediaGrabApp()
    app.mainloop()
