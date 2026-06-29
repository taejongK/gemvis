"""Chat engine that always searches first, then answers based on results."""

import json
import logging
from pathlib import Path

from gemvis.llm_client import extract_pdf_text, stream_chat
from gemvis.preferences import prefs
from gemvis.search import SearchEngine
from gemvis.web_search import fetch_page_text, search_duckduckgo

_TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".xml", ".toml",
    ".ini", ".cfg", ".log", ".sh", ".bash",
}
_MAX_FILE_CHARS = 8000  # per file


def _read_file_content(file_path: str) -> str:
    """Return raw text content of a file. Returns empty string on failure."""
    p = Path(file_path)
    if not p.exists():
        return ""
    suffix = p.suffix.lower()
    try:
        if suffix in _TEXT_SUFFIXES:
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > _MAX_FILE_CHARS:
                text = text[:_MAX_FILE_CHARS] + "\n... (truncated)"
            return text
        if suffix == ".pdf":
            return extract_pdf_text(p, max_chars=_MAX_FILE_CHARS)
    except Exception as e:
        logger.warning("[CHAT] failed to read %s: %s", file_path, e)
    return ""

logger = logging.getLogger(__name__)

_LANG_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}

FILE_ANSWER_SYSTEM = """\
당신은 Gemvis 개인 AI 비서입니다.
제공된 파일 요약과 웹 검색 결과를 바탕으로 사용자 질문에 답변하세요.

**중요한 답변 원칙:**
- 웹 결과의 "본문" 섹션을 적극 활용해 **구체적인 수치, 날짜, 고유명사, 사실** 을 직접 인용하세요. 두루뭉실한 요약("정보가 있습니다", "확인해보세요") 금지.
- 파일에서 찾은 정보를 언급할 때는 반드시 "[파일명]" 형식으로 출처를 표시하세요.
- 웹 결과에서 찾은 정보를 언급할 때는 "[웹: 제목]" 형식으로 출처를 표시하세요.
- 답변 마지막에 "---\\n**참고 파일:** 파일1, 파일2, ..." 와 "**참고 링크:** [제목](URL), ..." 형식으로 출처를 정리하세요. 실제로 인용한 출처만 적으세요.
- 마크다운 형식으로 답변하세요.
- 정보가 불충분하면 솔직히 알려주되, 본문에 답이 있다면 회피하지 마세요.\
"""


class ChatEngine:
    def __init__(self, search_engine: SearchEngine):
        self.search_engine = search_engine

    def chat(self, messages: list[dict], lang: str = "ko") -> dict:
        """Always search first, then answer based on results.

        Args:
            messages: Full conversation history [{role, content}, ...]
            lang: Language code for answer generation

        Returns:
            {answer, files, intent_type}
        """
        if not messages:
            return {"answer": "", "files": [], "intent_type": "file_search"}

        last_q = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        logger.info("[CHAT] ── new request ──────────────────────")
        logger.info("[CHAT] last user msg: %s", last_q[:200])

        try:
            result = self.search_engine.search(last_q, lang=lang)
        except Exception as e:
            logger.error("[CHAT] search failed: %s", e)
            return {
                "answer": "파일 검색 중 오류가 발생했습니다. 다시 시도해주세요.",
                "files": [],
                "intent_type": "file_search",
            }

        graph_results = result.get("graph_results", [])
        files = [
            {
                "file_id": r.get("name", ""),
                "file_name": Path(r.get("name", "")).name,
                "category": r.get("category"),
                "summary": r.get("summary"),
            }
            for r in graph_results
            if r.get("type") == "file" and r.get("name")
        ]
        logger.info("[CHAT] files found: %d", len(files))
        return {
            "answer": result.get("answer", ""),
            "files": files,
            "intent_type": "file_search",
        }

    def stream(self, messages: list[dict], lang: str = "ko", search_context: list[dict] | None = None):
        """Generator yielding SSE-style event dicts. Always searches first.

        Events:
            {"type": "meta", "intent_type": "file_search", "files": [...]}
            {"type": "chunk", "text": "..."}
            {"type": "error", "text": "..."}
            {"type": "done"}
        """
        if not messages:
            yield {"type": "done"}
            return

        last_q = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        logger.info("[STREAM] question=%s", last_q[:80])

        trimmed = self._prepare_messages(messages, max_turns=6)

        # Always search using the user's question; on failure, continue with empty results
        try:
            file_results = self.search_engine.retrieve(last_q, k=5, lang=lang)
        except Exception as e:
            logger.warning("[STREAM] search failed, continuing without results: %s", e)
            file_results = []

        logger.info("[STREAM] search returned %d results", len(file_results))

        files = [
            {
                "file_id": r.get("name", ""),
                "file_name": Path(r.get("name", "")).name,
                "category": r.get("category"),
                "summary": r.get("summary"),
            }
            for r in file_results
        ]
        # Optional web search — opt-in via preferences. Only the query text
        # leaves the device (no file content), and the user has explicitly
        # accepted that trade-off. Disabled by default.
        web_results: list[dict] = []
        if prefs.web_search_enabled:
            try:
                web_results = search_duckduckgo(last_q, max_results=5)
            except Exception as e:
                logger.warning("[STREAM] web search failed: %s", e)
                web_results = []
            logger.info("[STREAM] web returned %d results", len(web_results))

        yield {"type": "meta", "intent_type": "file_search", "files": files, "web": web_results}

        # Build RAG context: actual file content + metadata
        context_parts = []
        for r in file_results:
            file_path = r.get("name", "")
            name = Path(file_path).name
            lines = [f"[{name}]"]

            # Include metadata from raw_insight when available
            raw = r.get("raw_insight")
            if raw:
                try:
                    ins = json.loads(raw)
                    if ins.get("category"):
                        lines.append(f"카테고리: {ins['category']}")
                    if ins.get("tags"):
                        lines.append(f"태그: {', '.join(ins['tags'])}")
                    entities = ins.get("entities") or {}
                    entity_parts = []
                    for key, vals in entities.items():
                        if vals:
                            entity_parts.append(f"{key}: {', '.join(str(v) for v in vals)}")
                    if entity_parts:
                        lines.append("관련 엔티티: " + " | ".join(entity_parts))
                except (json.JSONDecodeError, TypeError):
                    pass
            elif r.get("category"):
                lines.append(f"카테고리: {r['category']}")

            # Include actual file content
            content = _read_file_content(file_path)
            if content:
                lines.append(f"\n--- 파일 내용 ---\n{content}")
            elif r.get("summary"):
                # Fallback to summary when file can't be read (image, binary, etc.)
                lines.append(f"\n--- 요약 ---\n{r['summary']}")

            context_parts.append("\n".join(lines))
        context_block = "\n\n".join(context_parts) if context_parts else "검색된 파일 없음"

        # Append web results to the prompt — clearly fenced so the LLM can
        # tell what's local file content vs external web snippet. For the
        # top 2 results, also fetch the actual page text so concrete data
        # (numbers, dates, etc.) is available rather than just snippets.
        web_block = ""
        if web_results:
            web_lines = []
            for i, w in enumerate(web_results, 1):
                block = (
                    f"[웹{i}] {w.get('title','')}\n"
                    f"URL: {w.get('url','')}\n"
                    f"요약: {w.get('snippet','')}"
                )
                if i <= 2:
                    page_text = fetch_page_text(w.get("url", ""), max_chars=2500)
                    if page_text:
                        block += f"\n본문:\n{page_text}"
                web_lines.append(block)
            web_block = "\n\n".join(web_lines)

        prompt_parts = [f"파일 정보:\n\n{context_block}"]
        if web_block:
            prompt_parts.append(f"웹 검색 결과:\n\n{web_block}")
        prompt_parts.append(f"질문: {last_q}")
        rag_messages = trimmed[:-1] + [{"role": "user", "content": "\n\n".join(prompt_parts)}]
        rag_system = FILE_ANSWER_SYSTEM + f"\n언어: {_LANG_NAMES.get(lang, 'Korean')}"
        try:
            for chunk in stream_chat(rag_messages, system=rag_system, temperature=0.5):
                yield {"type": "chunk", "text": chunk}
        except Exception as e:
            logger.error("[STREAM] rag stream failed: %s", e, exc_info=True)
            yield {"type": "error", "text": "답변 생성 중 오류가 발생했습니다."}

        yield {"type": "done"}

    def _prepare_messages(self, messages: list[dict], max_turns: int = 6) -> list[dict]:
        """Trim to last N turns and truncate long assistant messages."""
        window = messages[-(max_turns * 2):] if len(messages) > max_turns * 2 else messages
        result = []
        for m in window:
            if m.get("role") == "assistant" and len(m.get("content", "")) > 500:
                result.append({**m, "content": m["content"][:500] + "…"})
            else:
                result.append(m)
        return result
