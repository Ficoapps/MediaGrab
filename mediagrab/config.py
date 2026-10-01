from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .constants import (
    VALID_AUDIO_QUALITIES,
    VALID_LANGUAGES,
    VALID_MODES,
    VALID_VIDEO_QUALITIES,
)

APP_DIR = Path.home() / ".mediagrab"
CONFIG_FILE = APP_DIR / "config.json"


@dataclass
class AppConfig:
    output_dir: str = str(Path.home() / "Downloads" / "MediaGrab")
    mode: str = "all"
    language: str = "it"
    video_quality: str = "best"
    audio_quality: str = "best"
    port: int = 8765

    def normalize(self) -> None:
        if self.mode not in VALID_MODES:
            self.mode = "all"
        if self.language not in VALID_LANGUAGES:
            self.language = "it"
        if self.video_quality not in VALID_VIDEO_QUALITIES:
            self.video_quality = "best"
        if self.audio_quality not in VALID_AUDIO_QUALITIES:
            self.audio_quality = "best"
        if not isinstance(self.port, int) or not (1024 <= self.port <= 65535):
            self.port = 8765
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            self.output_dir = str(Path.home() / "Downloads" / "MediaGrab")

    @classmethod
    def load(cls) -> "AppConfig":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg

        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Configurazione non valida")
            known = {item.name for item in fields(cls)}
            cfg = cls(**{key: value for key, value in data.items() if key in known})
            cfg.normalize()
            return cfg
        except Exception:
            return cls()

    def save(self) -> None:
        self.normalize()
        APP_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = CONFIG_FILE.with_suffix(".json.tmp")
        temp_file.write_text(
            json.dumps(asdict(self), indent=2),
            encoding="utf-8",
        )
        temp_file.replace(CONFIG_FILE)
