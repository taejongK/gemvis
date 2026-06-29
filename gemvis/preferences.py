"""User-controlled preferences persisted to ~/.gemvis/preferences.json.

Distinct from CLAUDE config (.env) — these change at runtime via the UI.
"""

import json
import logging
import threading
from pathlib import Path

from gemvis.config import GRAPH_PATH

logger = logging.getLogger(__name__)

PREFS_PATH = GRAPH_PATH.parent / "preferences.json"

SUPPORTED_LANGS = {"ko", "en", "ja", "zh"}
DEFAULT_ANALYZE_LANG = "ko"


class UserPreferences:
    """Singleton-style preferences store. Disk-backed JSON."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Defaults — loaded values overlay this (only known keys are accepted).
        self._data: dict = {
            "analyze_lang": DEFAULT_ANALYZE_LANG,
            "watch_dirs": [],   # list[str] absolute paths; [] means "use defaults"
            "analyze_images": True,
            "web_search_enabled": False,  # opt-in; query text is sent to DuckDuckGo
            # LLM sampling parameters
            "llm_temperature": 0.1,  # 0.0 ~ 2.0
            "llm_max_tokens": 4096,  # 512 ~ 8192
            "llm_top_p": 0.95,       # 0.0 ~ 1.0
            "llm_top_k": 40,         # 1 ~ 100
        }
        self._load()

    def _load(self) -> None:
        if not PREFS_PATH.exists():
            return
        try:
            with open(PREFS_PATH, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self._data.update({k: v for k, v in loaded.items() if k in self._data})
        except Exception as e:
            logger.warning("Failed to load preferences: %s", e)

    def _save(self) -> None:
        try:
            PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PREFS_PATH, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to save preferences: %s", e)

    @property
    def analyze_lang(self) -> str:
        with self._lock:
            return self._data.get("analyze_lang", DEFAULT_ANALYZE_LANG)

    @analyze_lang.setter
    def analyze_lang(self, lang: str) -> None:
        if lang not in SUPPORTED_LANGS:
            return
        with self._lock:
            self._data["analyze_lang"] = lang
            self._save()

    @property
    def watch_dirs(self) -> list[str]:
        with self._lock:
            return list(self._data.get("watch_dirs", []) or [])

    @watch_dirs.setter
    def watch_dirs(self, dirs: list[str]) -> None:
        if not isinstance(dirs, list):
            return
        cleaned = [str(d) for d in dirs if isinstance(d, str) and d]
        with self._lock:
            self._data["watch_dirs"] = cleaned
            self._save()


    @property
    def analyze_images(self) -> bool:
        with self._lock:
            return bool(self._data.get("analyze_images", True))

    @analyze_images.setter
    def analyze_images(self, enabled: bool) -> None:
        with self._lock:
            self._data["analyze_images"] = bool(enabled)
            self._save()

    @property
    def web_search_enabled(self) -> bool:
        with self._lock:
            return bool(self._data.get("web_search_enabled", False))

    @web_search_enabled.setter
    def web_search_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._data["web_search_enabled"] = bool(enabled)
            self._save()

    @property
    def llm_temperature(self) -> float:
        with self._lock:
            return float(self._data.get("llm_temperature", 0.1))

    @llm_temperature.setter
    def llm_temperature(self, value: float) -> None:
        with self._lock:
            self._data["llm_temperature"] = max(0.0, min(2.0, float(value)))
            self._save()

    @property
    def llm_max_tokens(self) -> int:
        with self._lock:
            return int(self._data.get("llm_max_tokens", 4096))

    @llm_max_tokens.setter
    def llm_max_tokens(self, value: int) -> None:
        with self._lock:
            self._data["llm_max_tokens"] = max(512, min(8192, int(value)))
            self._save()

    @property
    def llm_top_p(self) -> float:
        with self._lock:
            return float(self._data.get("llm_top_p", 0.95))

    @llm_top_p.setter
    def llm_top_p(self, value: float) -> None:
        with self._lock:
            self._data["llm_top_p"] = max(0.0, min(1.0, float(value)))
            self._save()

    @property
    def llm_top_k(self) -> int:
        with self._lock:
            return int(self._data.get("llm_top_k", 40))

    @llm_top_k.setter
    def llm_top_k(self, value: int) -> None:
        with self._lock:
            self._data["llm_top_k"] = max(1, min(100, int(value)))
            self._save()


prefs = UserPreferences()
