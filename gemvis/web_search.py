"""DuckDuckGo HTML web search — opt-in only.

Privacy note: the user's query text is sent to duckduckgo.com.  No file
content, no telemetry — only the literal search phrase.  Disabled by
default (see ``preferences.web_search_enabled``).
"""

import logging
import re
import urllib.parse
import urllib.request
from html import unescape

logger = logging.getLogger(__name__)

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
)

_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_url(href: str) -> str:
    """DuckDuckGo wraps outgoing links in `/l/?uddg=...`. Unwrap that."""
    if "uddg=" in href:
        try:
            return urllib.parse.unquote(href.split("uddg=", 1)[1].split("&", 1)[0])
        except Exception:
            return href
    return href


def _strip(html: str) -> str:
    return unescape(_TAG_RE.sub("", html)).strip()


_SCRIPT_STYLE_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HEAD_RE = re.compile(r"<head[^>]*>.*?</head>", re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"\s+")


def fetch_page_text(url: str, max_chars: int = 3000, timeout: float = 6.0) -> str:
    """Fetch a web page and return a plain-text excerpt of its body.

    Best-effort: scripts/styles/<head> stripped, all tags removed, whitespace
    collapsed. Returns "" on failure (so callers can degrade gracefully).
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Honour reasonable size limits (3MB cap on raw read)
            raw = resp.read(3_000_000)
            ctype = resp.headers.get("Content-Type", "").lower()
            if "text/html" not in ctype and "text/plain" not in ctype:
                return ""
        # Decode (try utf-8 first, fall back with replace)
        try:
            html = raw.decode("utf-8")
        except UnicodeDecodeError:
            html = raw.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("[WEB_SEARCH] fetch_page_text failed for %s: %s", url[:80], e)
        return ""

    # Strip script/style/head and all tags
    html = _SCRIPT_STYLE_RE.sub(" ", html)
    html = _HEAD_RE.sub(" ", html)
    text = _strip(html)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + " …"
    return text


def search_duckduckgo(query: str, max_results: int = 5, timeout: float = 8.0) -> list[dict]:
    """Return up to ``max_results`` web results for ``query``.

    Each item: ``{"title": str, "snippet": str, "url": str}``.
    Returns ``[]`` on any network/parse failure — never raises so the
    chat path always has a sensible fallback.
    """
    q = (query or "").strip()
    if not q:
        return []

    try:
        data = urllib.parse.urlencode({"q": q, "kl": "wt-wt"}).encode("utf-8")
        req = urllib.request.Request(
            DDG_HTML_URL,
            data=data,
            headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("[WEB_SEARCH] fetch failed: %s", e)
        return []

    out: list[dict] = []
    for m in _RESULT_RE.finditer(html):
        url = _clean_url(m.group(1))
        title = _strip(m.group(2))
        snippet = _strip(m.group(3))
        if not (title and url):
            continue
        out.append({"title": title, "snippet": snippet, "url": url})
        if len(out) >= max_results:
            break
    logger.info("[WEB_SEARCH] %r → %d results", q[:60], len(out))
    return out
