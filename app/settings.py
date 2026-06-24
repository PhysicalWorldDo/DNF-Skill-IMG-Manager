from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT_SOURCE_DIR = Path("E:/WeGameApps/地下城与勇士：创新世纪/ImagePacks2")


def tool_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent.parent
    return Path(__file__).resolve().parents[1]


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def config_dir() -> Path:
    return tool_root() / "config"


def data_dir() -> Path:
    return tool_root() / "data"


def skill_pages_dir() -> Path:
    return app_root() / "data" / "skill_pages"


class Settings:
    def __init__(self, path: Path | None = None):
        self.path = path or config_dir() / "settings.json"
        self._data: dict[str, object] = {}
        self.load()

    def load(self) -> None:
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_str(self, key: str, default: str = "") -> str:
        value = self._data.get(key, default)
        return str(value) if value is not None else default

    def set_str(self, key: str, value: str) -> None:
        self._data[key] = value
