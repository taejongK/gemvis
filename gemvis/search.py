"""Conversational search using a local OpenAI-compatible LLM + knowledge graph traversal."""

import json
import logging
import re

from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.llm_client import complete_text

logger = logging.getLogger(__name__)

INTENT_PROMPT = """\
You are a search intent parser for Gemvis, a personal file assistant.
The user's files are stored in a knowledge graph with nodes of type:
  file, person, place, project, event, date, tag
Date nodes use "YYYY-MM-DD" format (e.g. "2026-04-14").

The search uses HYBRID matching:
  1. `search_terms` → EXACT/substring match on node names, tags, categories
     (fast, precise — use for named entities, dates, explicit tags)
  2. `semantic_query` → EMBEDDING similarity against file summaries+tags
     (fuzzy, meaning-based — use for topics, feelings, subjects, descriptions)

Given the user's question, output a JSON object with these fields:

- "search_terms": list[str]
  Structural keywords the user literally mentions. Include:
    • proper nouns (people, places, projects) as-is
    • dates CONVERTED to YYYY-MM-DD (e.g. "2026년 4월" → "2026-04",
      "지난달" → inferred month if possible, else omit)
    • explicit tag-like words ("회의", "사진", "영수증" only if user refers to them as a category)
  Omit generic verbs, adjectives, or fuzzy concepts. Empty list [] if question is purely semantic.

- "node_types": list[str]
  Filter to specific node types if the user explicitly asks for one
  (e.g. "누가" → ["person"], "어디서" → ["place"]). Else [].

- "categories": list[str]
  STRICT category filter for files. Only include when the user clearly asks
  for a specific kind of file. Use the exact values:
    • "photo" / "screenshot"  ← 이미지/사진/스크린샷/그림
    • "document"              ← 문서/PDF/리포트
    • "memo"                  ← 메모/노트
    • "voice_memo"            ← 음성/녹음/오디오
    • "code"                  ← 코드/소스
    • "data"                  ← 데이터/CSV/JSON/엑셀
    • "other"
  If the user did NOT specify a file kind, leave this list EMPTY [].

- "semantic_query": str
  A short Korean phrase (2-6 words) describing the TOPIC / MEANING of what
  the user wants. This is the content/vibe/subject of the files.
  Think: "if I had to describe the file's content in 1 phrase, what would it be?"
  Empty string "" ONLY if the question is purely a lookup by name/date (no topical aspect).

- "intent": brief one-line description of what the user wants.

---

EXAMPLES:

Q: "지난달 김과장이랑 간 식당 어디였어?"
A: {{
  "search_terms": ["김과장"],
  "node_types": [],
  "semantic_query": "식당 외식 모임",
  "intent": "김과장과 함께 간 식당 위치"
}}

Q: "Gemvis 프로젝트 관련 회의록 찾아줘"
A: {{
  "search_terms": ["Gemvis"],
  "node_types": [],
  "semantic_query": "회의록 프로젝트 논의",
  "intent": "Gemvis 프로젝트 회의 관련 파일"
}}

Q: "2026년 3월에 찍은 가족 사진"
A: {{
  "search_terms": ["2026-03"],
  "node_types": [],
  "semantic_query": "가족 사진 나들이",
  "intent": "2026년 3월 가족 사진"
}}

Q: "최근 읽은 논문 요약"
A: {{
  "search_terms": [],
  "node_types": [],
  "semantic_query": "논문 요약 연구 자료",
  "intent": "최근 논문 관련 파일"
}}

Q: "김철수가 누구야"
A: {{
  "search_terms": ["김철수"],
  "node_types": ["person"],
  "semantic_query": "",
  "intent": "김철수 엔티티 조회"
}}

Q: "해커톤 아이디어들"
A: {{
  "search_terms": ["해커톤"],
  "node_types": [],
  "semantic_query": "아이디어 브레인스토밍 구상",
  "intent": "해커톤 관련 아이디어 파일"
}}

Q: "행복해 보이는 사진 보여줘"
A: {{
  "search_terms": [],
  "node_types": ["file"],
  "categories": ["photo", "screenshot"],
  "semantic_query": "행복한 장면 미소 웃음",
  "intent": "긍정적 분위기의 사진"
}}

Q: "이미지 파일 찾아줘"
A: {{
  "search_terms": [],
  "node_types": ["file"],
  "categories": ["photo", "screenshot"],
  "semantic_query": "",
  "intent": "이미지 파일 전체 조회"
}}

Q: "PDF 문서 보여줘"
A: {{
  "search_terms": [],
  "node_types": ["file"],
  "categories": ["document"],
  "semantic_query": "",
  "intent": "문서 파일 조회"
}}

Q: "회의 녹음 파일"
A: {{
  "search_terms": ["회의"],
  "node_types": ["file"],
  "categories": ["voice_memo"],
  "semantic_query": "회의 음성 기록",
  "intent": "회의 녹음 파일"
}}

---

Return ONLY valid JSON matching the shape above. No markdown fences, no explanation.

{context_block}User question: {question}
"""

CONTEXT_BLOCK = """\
--- Previous turn context ---
Previous question intent: {prev_intent}
Search terms used: {prev_search_terms}
Categories filtered: {prev_categories}
Results: {prev_file_count} files found ({prev_file_names})
---
The current question may be a follow-up. If the user references previous results
("그 중에서", "그거", "첫 번째", "나머지", "거기서" etc.), MERGE the previous
search context with the new request.
Example: previous search_terms=["김과장"], user now says "그 중에서 PDF만"
→ keep search_terms=["김과장"], ADD categories=["document"].

"""

ANSWER_PROMPT = """\
You are a helpful personal file assistant. Answer the user's question in {language} based on the search results from their knowledge graph.

IMPORTANT RULES:
1. The "matched_files" list below is EXACTLY what the user will see in their UI. Your answer MUST agree on the count.
2. If there are matched files, start your answer with a natural phrase in {language} like "Found {file_count} files:" and then list them.
3. Do NOT cherry-pick "most relevant" — list ALL matched files (up to 10; mention the rest as "and N more" if there are more).
4. Mention file names (not full paths). Use a bullet list for readability.
5. If matched_files is empty, say so politely in {language} and suggest what to try.
6. Related entities (people, places, tags) can be mentioned briefly as context, but do not replace the file list.

User question: {question}

Matched files ({file_count}):
{file_list}

Related context entities:
{other_context}

Reminder: respond entirely in {language}.
"""


_LANG_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}


class SearchEngine:
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def retrieve(self, question: str, k: int = 5, lang: str = "ko") -> list[dict]:
        """Return top-k file results without generating an answer."""
        intent = self._parse_intent(question, prev_context=None)
        results = self._search_graph(intent)
        return [r for r in results if r.get("type") == "file"][:k]

    def search(self, question: str, prev_context: dict | None = None, lang: str = "ko") -> dict:
        """Process a natural language question. Returns dict with answer, intent, results."""
        intent = self._parse_intent(question, prev_context)
        results = self._search_graph(intent)
        answer = self._generate_answer(question, results, prev_context=prev_context, lang=lang)

        # Build carry-forward context for the next turn
        from pathlib import Path as _Path
        file_results = [r for r in results if r.get("type") == "file"]
        context = {
            "intent": intent,
            "file_count": len(file_results),
            "file_names": [_Path(r.get("name", "")).name for r in file_results[:10]],
            "categories_found": sorted(set(
                r.get("category", "") for r in file_results if r.get("category")
            )),
        }

        return {
            "answer": answer,
            "intent": intent,
            "graph_results": results,
            "context": context,
        }

    @staticmethod
    def _strip_fences(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        return raw.strip()

    # Characters that signal a complex/conversational question — trigger LLM path
    _COMPLEX_QUERY_PATTERN = re.compile(r"[?!,.…;。、]|누구|어디|언제|무엇|어떻|왜|한테|에게|관련|찾아|보여|알려")

    # Korean → category mapping for rule-based detection
    _CATEGORY_KEYWORDS = {
        "이미지": ["photo", "screenshot"],
        "사진": ["photo", "screenshot"],
        "스크린샷": ["screenshot"],
        "그림": ["photo", "screenshot"],
        "문서": ["document"],
        "pdf": ["document"],
        "리포트": ["document"],
        "메모": ["memo"],
        "노트": ["memo"],
        "음성": ["voice_memo"],
        "녹음": ["voice_memo"],
        "오디오": ["voice_memo"],
        "코드": ["code"],
        "데이터": ["data"],
        "csv": ["data"],
        "json": ["data"],
    }

    # Generic words that shouldn't be used as structural search terms
    _STOPWORDS = {
        "파일", "파일들", "files", "file",
        "찾아줘", "찾아", "보여줘", "보여", "알려줘", "알려",
        "관련", "내용", "것", "거",
    }

    def _detect_categories(self, text: str) -> list[str]:
        """Detect category filter words in a query and return matching categories."""
        lower = text.lower()
        found: set[str] = set()
        for keyword, cats in self._CATEGORY_KEYWORDS.items():
            if keyword in lower:
                found.update(cats)
        return sorted(found)

    def _is_simple_query(self, question: str) -> bool:
        """True if the query is short and structural enough to skip the LLM."""
        q = question.strip()
        if not q or len(q) > 40:
            return False
        if self._COMPLEX_QUERY_PATTERN.search(q):
            return False
        tokens = q.split()
        return len(tokens) <= 3

    def _rule_based_intent(self, question: str) -> dict:
        """Fast path: rule-based intent parsing (no LLM).

        Used for simple keyword queries like "회의", "김철수 2024-03", "가족 사진".
        """
        q = question.strip()
        tokens = q.split()
        categories = self._detect_categories(q)
        # Drop category words (e.g. "이미지") and generic stopwords ("파일")
        category_words = set(self._CATEGORY_KEYWORDS.keys())
        skip = category_words | self._STOPWORDS
        filtered_tokens = [t for t in tokens if t.lower() not in skip]
        return {
            "search_terms": filtered_tokens,
            "node_types": [],
            "categories": categories,
            "semantic_query": q if not categories or filtered_tokens else "",
            "intent": q,
        }

    def _build_context_block(self, prev_context: dict) -> str:
        """Build a compact context block string from previous turn context."""
        prev_intent = prev_context.get("intent", {})
        return CONTEXT_BLOCK.format(
            prev_intent=prev_intent.get("intent", ""),
            prev_search_terms=prev_intent.get("search_terms", []),
            prev_categories=prev_intent.get("categories", []),
            prev_file_count=prev_context.get("file_count", 0),
            prev_file_names=", ".join(prev_context.get("file_names", [])[:5]),
        )

    def _parse_intent(self, question: str, prev_context: dict | None = None) -> dict:
        """Parse intent — rule-based fast path for simple queries, LLM for complex ones."""
        # Follow-up questions always need LLM (rule-based can't resolve references)
        if self._is_simple_query(question) and not prev_context:
            logger.info("Using rule-based intent parsing for: %r", question)
            return self._rule_based_intent(question)

        context_block = self._build_context_block(prev_context) if prev_context else ""

        try:
            raw = complete_text(INTENT_PROMPT.format(
                question=question,
                context_block=context_block,
            ))
            parsed = json.loads(self._strip_fences(raw))
            parsed.setdefault("search_terms", [])
            parsed.setdefault("node_types", [])
            parsed.setdefault("categories", [])
            parsed.setdefault("semantic_query", "")
            parsed.setdefault("intent", question)
            # Safety net: backfill categories from question keywords if LLM missed them
            if not parsed["categories"]:
                detected = self._detect_categories(question)
                if detected:
                    parsed["categories"] = detected
            return parsed
        except Exception as e:
            logger.error("LLM intent parsing failed, falling back to rules: %s", e)
            return self._rule_based_intent(question)

    def _normalize_date_term(self, term: str) -> list[str]:
        """Expand a date term into multiple search-friendly formats."""
        variants = [term]
        # "2026년 4월 14일" → "2026-04-14"
        m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", term)
        if m:
            variants.append(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
        # Already YYYY-MM-DD
        if re.match(r"\d{4}-\d{2}-\d{2}", term):
            variants.append(term)
        return variants

    def _files_matching_term(self, term: str, node_types: list[str]) -> tuple[set[str], list[dict]]:
        """Return (set of file IDs, all matched nodes) where a file "matches" a term if:
        - its name/summary/category contains the term, OR
        - it is connected (1-hop) to an entity node (tag/person/place/project/event/date)
          whose name contains the term.
        """
        entity_types = {"tag", "person", "place", "project", "event", "date"}

        # All variants (e.g. "2026년 4월" → "2026-04")
        variants = self._normalize_date_term(term)

        matched_nodes: list[dict] = []
        for v in variants:
            if node_types:
                for nt in node_types:
                    matched_nodes.extend(self.graph.search_nodes(v, node_type=nt))
            else:
                matched_nodes.extend(self.graph.search_nodes(v))

        # Deduplicate matched nodes
        seen_nodes = set()
        deduped_nodes = []
        for n in matched_nodes:
            if n["id"] not in seen_nodes:
                seen_nodes.add(n["id"])
                deduped_nodes.append(n)

        # Collect file IDs: direct matches + 1-hop from entity matches
        file_ids: set[str] = set()
        for n in deduped_nodes:
            nt = n.get("type")
            if nt == "file":
                file_ids.add(n["id"])
            elif nt in entity_types:
                for neighbor in self.graph.get_neighbors(n["id"]):
                    if neighbor.get("type") == "file":
                        file_ids.add(neighbor["id"])
        return file_ids, deduped_nodes

    def _search_graph(self, intent: dict) -> list[dict]:
        """Search the knowledge graph with hybrid KG (structural) + embedding (semantic) ranking.

        Multiple search_terms are combined with AND semantics — a file must match
        every term (directly or via a connected entity) to be included.
        """
        search_terms = intent.get("search_terms", [])
        node_types = intent.get("node_types", [])
        categories: list[str] = intent.get("categories", []) or []
        semantic_query = (intent.get("semantic_query") or "").strip()

        entity_types = {"tag", "person", "place", "project", "event"}

        # ── Stage 1: Structural filtering (AND across search_terms) ─────────────
        matched_file_ids: set[str] | None = None
        all_term_matched_nodes: list[dict] = []  # preserve entity context for UI

        for term in search_terms:
            term_files, term_nodes = self._files_matching_term(term, node_types)
            all_term_matched_nodes.extend(term_nodes)
            if matched_file_ids is None:
                matched_file_ids = term_files
            else:
                matched_file_ids &= term_files  # AND

        if matched_file_ids is None:
            matched_file_ids = set()

        # Build the ordered enriched list: files first, then related entities
        enriched: list[dict] = []
        seen = set()

        # Files that satisfied the AND filter
        for fid in matched_file_ids:
            node_type, name = fid.split(":", 1)
            nd = self.graph._node_to_dict(self.graph._node_uri(node_type, name))
            if nd and nd["id"] not in seen:
                enriched.append(nd)
                seen.add(nd["id"])

        # Plus entity nodes that matched any term (as context) — NOT as primary results
        seen_entity_ids = set()
        for n in all_term_matched_nodes:
            if n.get("type") in entity_types and n["id"] not in seen_entity_ids:
                seen_entity_ids.add(n["id"])
                if n["id"] not in seen:
                    enriched.append(n)
                    seen.add(n["id"])

        # If only categories were specified (no terms), pull every matching file
        if not enriched and not search_terms and categories:
            for f in self.graph.get_file_nodes():
                if f.get("category") in categories and f["id"] not in seen:
                    enriched.append(f)
                    seen.add(f["id"])

        # "recent/최근" fallback
        if not enriched and any(kw in " ".join(search_terms).lower() for kw in ["최근", "recent", "새로운", "마지막"]):
            enriched = self.graph.get_file_nodes()[:5]

        # Semantic fallback when structural search is empty (covers two cases):
        #   1. No search_terms at all (purely semantic question)
        #   2. search_terms exist but AND filter found nothing (e.g. "이미지 파일")
        # In both cases, fall back to embedding similarity if a semantic_query
        # is available. We use the original question if semantic_query is missing.
        if not enriched and self.graph.embeddings.count() > 0:
            fallback_query = semantic_query or " ".join(search_terms).strip()
            if fallback_query:
                top = self.graph.embeddings.top_k(fallback_query, k=20)
                for node_id, _score in top:
                    if node_id in seen or not self.graph.has_node(node_id):
                        continue
                    node_type, name = node_id.split(":", 1)
                    node_dict = self.graph._node_to_dict(
                        self.graph._node_uri(node_type, name)
                    )
                    if node_dict:
                        enriched.append(node_dict)
                        seen.add(node_id)

        # ── Always split by type, re-rank files (if embeddings available), merge ──
        file_results = [r for r in enriched if r.get("type") == "file"]
        other_results = [r for r in enriched if r.get("type") != "file"]

        # Strict category filter: when the user asks for a specific kind of file,
        # drop files whose category doesn't match. This prevents the semantic
        # fallback from returning unrelated file types.
        if categories:
            file_results = [
                r for r in file_results
                if r.get("category") in categories
            ]

        if (
            semantic_query
            and self.graph.embeddings.count() > 0
            and file_results
        ):
            file_ids = [r["id"] for r in file_results]
            scores = self.graph.embeddings.score(semantic_query, node_ids=file_ids)
            scored = [(r, scores.get(r["id"], 0.0)) for r in file_results]
            scored.sort(key=lambda x: x[1], reverse=True)
            file_results = [r for r, _ in scored]

        # File nodes always come first so they survive the 50-item cap
        return (file_results + other_results)[:50]

    def _generate_answer(self, question: str, results: list[dict], prev_context: dict | None = None, lang: str = "ko") -> str:
        """Generate a natural language answer from search results."""
        from gemvis.i18n import t
        # Split files from other entities so the LLM answer stays consistent with UI
        from pathlib import Path
        file_results = [r for r in results if r.get("type") == "file"]
        other_results = [r for r in results if r.get("type") != "file"]

        if not file_results and not other_results:
            return t("search.noResults", lang=lang)

        # Simplified file list (display name + summary only)
        file_list_lines = []
        for r in file_results:
            raw_name = r.get("name", r.get("id", ""))
            display = Path(raw_name).name if raw_name else r.get("id", "?")
            summary = (r.get("summary") or "").strip()
            line = f"- {display}"
            if summary:
                line += f": {summary}"
            file_list_lines.append(line)
        file_list_text = "\n".join(file_list_lines) if file_list_lines else "-"

        # Compact other-context: type:name only
        other_text = ", ".join(
            f"{r.get('type')}:{r.get('name','?')}" for r in other_results[:20]
        ) if other_results else "-"

        # Add follow-up hint if this is a continuation
        display_question = question
        if prev_context:
            prev_intent_str = prev_context.get("intent", {}).get("intent", "")
            if prev_intent_str:
                display_question = f"{question}\n(이전 검색: {prev_intent_str})"

        try:
            return complete_text(
                ANSWER_PROMPT.format(
                    question=display_question,
                    file_count=len(file_results),
                    file_list=file_list_text,
                    other_context=other_text,
                    language=_LANG_NAMES.get(lang, "Korean"),
                )
            )
        except Exception as e:
            logger.error("Answer generation failed: %s", e)
            # Fallback: deterministic local answer (no LLM)
            if file_results:
                return t("search.foundFiles", lang=lang, count=len(file_results), files=file_list_text)
            return t("search.genericError", lang=lang)
