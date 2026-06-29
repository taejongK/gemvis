"""Configuration management for Gemvis."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# OpenAI-compatible LLM endpoint (e.g. llama-server, vLLM)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://172.20.64.1:8080/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "none")
LLM_MODEL = os.environ.get("LLM_MODEL", "unsloth/gemma-4-E2B-it-GGUF:Q4_K_M")


def _normalize_path(p: str) -> str:
    """Cross-OS path normalization. Convert Git Bash POSIX (/c/Users/...) to Windows (C:\\Users\\...)."""
    if not p:
        return ""
    p = p.strip()
    if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[1].isalpha() and p[2] == "/":
        drive = p[1].upper()
        rest = p[3:].replace("/", os.sep)
        return f"{drive}:{os.sep}{rest}"
    return p


def _resolve_dir(p: str) -> Path | None:
    """Normalize and resolve a path string to a Path. Returns None if blank."""
    p = _normalize_path(p)
    if not p:
        return None
    return Path(p).expanduser().resolve()


def _default_watch_dirs() -> list[Path]:
    """OS-standard default watch folders + the dedicated ~/gemvis_watch.

    Documents / Downloads / Pictures are included only if they already exist.
    The ~/gemvis_watch folder is always included; if missing it's created so
    the user has a clear scratch area to drop files into.
    """
    home = Path.home()
    standard = [home / "Documents", home / "Downloads", home / "Pictures"]
    out = [p for p in standard if p.exists()]
    gemvis_watch = home / "gemvis_watch"
    try:
        gemvis_watch.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only home (rare); fall through with whatever standard dirs we have.
        if not out:
            return []
    if gemvis_watch.exists():
        out.append(gemvis_watch)
    return out


def _parse_watch_dirs(env_value: str) -> list[Path]:
    """Parse comma-separated paths from env var."""
    if not env_value or not env_value.strip():
        return []
    out: list[Path] = []
    for piece in env_value.split(","):
        resolved = _resolve_dir(piece)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


# Read user-saved watch_dirs directly from the prefs file (avoid circular
# import with gemvis.preferences which itself depends on this module).
def _load_user_watch_dirs() -> list[Path]:
    prefs_path = Path.home() / ".gemvis" / "preferences.json"
    if not prefs_path.exists():
        return []
    try:
        with open(prefs_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    raw = data.get("watch_dirs") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[Path] = []
    for piece in raw:
        if not isinstance(piece, str):
            continue
        resolved = _resolve_dir(piece)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


# Resolution order:
#   1. GEMVIS_WATCH_DIRS / GEMVIS_WATCH_DIR env vars (developer override)
#   2. user preferences file (~/.gemvis/preferences.json) — most recent UI save
#   3. _default_watch_dirs() — Documents/Downloads/Pictures/gemvis_watch
_env_dirs = _parse_watch_dirs(os.environ.get("GEMVIS_WATCH_DIRS", ""))
if not _env_dirs:
    _legacy = _resolve_dir(os.environ.get("GEMVIS_WATCH_DIR", ""))
    if _legacy:
        _env_dirs = [_legacy]

if _env_dirs:
    WATCH_DIRS: list[Path] = _env_dirs
else:
    _user_dirs = _load_user_watch_dirs()
    WATCH_DIRS = _user_dirs if _user_dirs else _default_watch_dirs()

# Backward-compat alias for any code that still references the singular form.
# Empty list (no default folders existed) falls back to ~/gemvis_watch.
WATCH_DIR: Path = WATCH_DIRS[0] if WATCH_DIRS else Path.home() / "gemvis_watch"

# Suggested defaults (always returned to UI so users can re-enable after toggling off)
DEFAULT_WATCH_DIRS: list[Path] = _default_watch_dirs() or [Path.home() / "gemvis_watch"]


GRAPH_PATH = Path(os.environ.get("GEMVIS_GRAPH_PATH", Path.home() / ".gemvis" / "graph.ttl"))
EMBEDDINGS_PATH = Path(os.environ.get("GEMVIS_EMBEDDINGS_PATH", Path.home() / ".gemvis" / "embeddings.npz"))
EMBEDDING_MODEL = os.environ.get(
    "GEMVIS_EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
EVENTS_PATH = Path(os.environ.get("GEMVIS_EVENTS_PATH", Path.home() / ".gemvis" / "events.ttl"))

SUPPORTED_EXTENSIONS = {
    "text": {".txt", ".md", ".csv", ".json", ".log"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"},
    "document": {".pdf"},
}

ALL_EXTENSIONS = set()
for exts in SUPPORTED_EXTENSIONS.values():
    ALL_EXTENSIONS.update(exts)

# Directory parts that should never be watched/scanned. If any segment of a
# file's path matches one of these, the file is skipped entirely. Prevents
# pathological cases like watching a project root that contains node_modules
# or a Python venv (which can pull in tens of thousands of files).
WATCH_IGNORE_PARTS = frozenset({
    "node_modules",
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".cache",
    ".next",
    "dist",
    "build",
    ".gemvis",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
})


def is_ignored_path(path: Path) -> bool:
    """Return True if any part of *path* is in WATCH_IGNORE_PARTS."""
    return any(part in WATCH_IGNORE_PARTS for part in path.parts)


GEMINI_MODEL = "gemma-4-31b-it"


def ensure_dirs():
    """Create necessary directories if they don't exist."""
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Watch dirs are user-owned (Downloads/Pictures/...) — don't auto-create.
    # If a configured watch dir is missing, the watcher logs a warning and skips it.
