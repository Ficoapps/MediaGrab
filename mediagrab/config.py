from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

APP_DIR = Path.home() / ".mediagrab"
CONFIG_FILE = APP_DIR / "config.json"


@dataclass
class AppConfig:
    output_dir: str = str(Path.home() / "Downloads" / "MediaGrab")
    mode: str = "all"  # video | images | all
    port: int = 8765

    @classmethod
    def load(cls) -> "AppConfig":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return cls(**{**asdict(cls()), **data})
        except Exception:
            return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
