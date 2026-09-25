from __future__ import annotations

import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import AppConfig
from .downloader import download_url
from .server import LocalServer

MODE_LABELS = {
    "Tutto (video + immagini)": "all",
    "Solo video": "video",
    "Solo immagini": "images",
}
MODE_LABELS_REVERSE = {v: k for k, v in MODE_LABELS.items()}


class MediaGrabApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaGrab 0.2")
        self.geometry("760x560")
        self.minsize(680, 480)

        self.config_data = AppConfig.load()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.server = LocalServer(self.config_data, self.log)

        self.url_var = tk.StringVar()
        self.output_var = tk.StringVar(value=self.config_data.output_dir)
        self.mode_var = tk.StringVar(value=MODE_LABELS_REVERSE.get(self.config_data.mode, "Tutto (video + immagini)"))
        self.server_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Pronto")

        self._build_ui()
        self.after(100, self._drain_logs)
        self.after(250, self._start_server)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="MediaGrab 0.2", font=("Segoe UI", 20, "bold"))
        title.pack(anchor="w")
        ttk.Label(root, text="Rileva e scarica media pubblicamente accessibili dalle pagine che puoi visualizzare.").pack(anchor="w", pady=(0, 16))

        form = ttk.Frame(root)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="URL").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(form, textvariable=self.url_var).grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(form, text="Cartella").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=6)
        out_row = ttk.Frame(form)
        out_row.grid(row=1, column=1, sticky="ew", pady=6)
        out_row.columnconfigure(0, weight=1)
        ttk.Entry(out_row, textvariable=self.output_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(out_row, text="Sfoglia…", command=self._choose_folder).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(form, text="Modalità").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        combo = ttk.Combobox(form, textvariable=self.mode_var, values=list(MODE_LABELS), state="readonly")
        combo.grid(row=2, column=1, sticky="ew", pady=6)
        combo.bind("<<ComboboxSelected>>", lambda _: self._save_config())

        server_check = ttk.Checkbutton(
            form,
            text="Attiva collegamento con estensione Chrome/Edge",
            variable=self.server_var,
            command=self._toggle_server,
        )
        server_check.grid(row=3, column=1, sticky="w", pady=8)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(10, 12))
        self.download_btn = ttk.Button(actions, text="Scarica", command=self._download_clicked)
        self.download_btn.pack(side="left")
        ttk.Button(actions, text="Apri cartella", command=self._open_folder).pack(side="left", padx=8)
        ttk.Label(actions, textvariable=self.status_var).pack(side="right")

        ttk.Separator(root).pack(fill="x", pady=(0, 8))
        ttk.Label(root, text="Attività", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.log_text = tk.Text(root, height=17, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_var.get())
        if selected:
            self.output_var.set(selected)
            self._save_config()

    def _save_config(self) -> None:
        self.config_data.output_dir = self.output_var.get().strip()
        self.config_data.mode = MODE_LABELS.get(self.mode_var.get(), "all")
        self.config_data.save()

    def _download_clicked(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("MediaGrab", "Inserisci l'indirizzo della pagina da scaricare.")
            return
        self._save_config()
        self.download_btn.configure(state="disabled")
        self.status_var.set("Download in corso…")

        def run():
            try:
                download_url(url, self.config_data.output_dir, self.config_data.mode, self.log)
                self.log("Operazione completata.")
                self.after(0, lambda: self.status_var.set("Completato"))
            except Exception as exc:
                self.log(f"Errore: {exc}")
                self.after(0, lambda: self.status_var.set("Errore"))
            finally:
                self.after(0, lambda: self.download_btn.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

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
                self.log(f"Impossibile avviare il connettore browser: {exc}")
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
