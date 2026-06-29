"""Tiny backend i18n that shares the frontend's translations.json."""

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRANSLATIONS_PATH = _REPO_ROOT / "frontend" / "src" / "locales" / "translations.json"

SUPPORTED = {"ko", "en", "ja", "zh"}
DEFAULT_LANG = "ko"

_cache: dict[str, Any] | None = None


def _load() -> dict[str, Any]:
    global _cache
    if _cache is None:
        with open(_TRANSLATIONS_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def extract_lang(accept_language: str | None) -> str:
    """Parse an Accept-Language header. Returns a supported code or DEFAULT_LANG."""
    if not accept_language:
        return DEFAULT_LANG
    primary = accept_language.split(",")[0].strip().lower()
    code = primary.split("-")[0]
    return code if code in SUPPORTED else DEFAULT_LANG


def t(key: str, lang: str = DEFAULT_LANG, **params: Any) -> str:
    """Translate a dot-separated key. Falls back lang → ko → en → key."""
    node: Any = _load()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]
    if not isinstance(node, dict):
        return key
    text = node.get(lang) or node.get("ko") or node.get("en") or key
    if not isinstance(text, str):
        return key
    for k, v in params.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text
