"""GemInsight generation using a local OpenAI-compatible LLM (llama-server).

GemInsight is the core reference data extracted by Gemma 4 from each file.
It serves as the Single Source of Truth (SSoT) for all downstream features:
- Knowledge Graph (structure)
- Embeddings (semantics)
- EventLog (timeline)
- Dashboard, Calendar, Graph View, Chat Search (UI)
"""

import json
import logging
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from pathlib import Path
from typing import Literal

from gemvis.config import SUPPORTED_EXTENSIONS
from gemvis.llm_client import complete_text, complete_image, extract_pdf_text, complete_with_tools

AnalysisStatus = Literal["pending", "processing", "completed", "failed"]

logger = logging.getLogger(__name__)

LANG_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}


def get_analysis_prompt(lang: str = "ko") -> str:
    language = LANG_NAMES.get(lang, "Korean")
    return (
        f"You are a file analysis assistant. Analyze the given file and extract structured metadata. "
        f"Use the analyze_file function to return your analysis. "
        f"Write all natural-language fields (summary, tags) in {language}."
    )


def get_analysis_tool(lang: str = "ko") -> dict:
    language = LANG_NAMES.get(lang, "Korean")
    return {
        "type": "function",
        "function": {
            "name": "analyze_file",
            "description": "Extract structured metadata from a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["memo", "photo", "screenshot", "document", "voice_memo", "code", "data", "other"],
                        "description": "File category based on content type",
                    },
                    "summary": {
                        "type": "string",
                        "description": f"One-line summary in {language}",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 3,
                        "maxItems": 7,
                        "description": f"Relevant tags in {language}. Include a content-type tag (e.g. image, document, audio, code) translated into {language}.",
                    },
                "entities": {
                    "type": "object",
                    "properties": {
                        "people": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Person names mentioned in the file",
                        },
                        "places": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Place names mentioned in the file",
                        },
                        "projects": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Project names mentioned in the file",
                        },
                        "dates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dates mentioned in the file (normalize to YYYY-MM-DD if possible)",
                        },
                        "events": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Event names mentioned in the file",
                        },
                    },
                    "required": ["people", "places", "projects", "dates", "events"],
                },
                "relations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "source": {"type": "string"},
                            "source_type": {
                                "type": "string",
                                "enum": ["person", "place", "project", "event", "date", "tag"],
                            },
                            "target": {"type": "string"},
                            "target_type": {
                                "type": "string",
                                "enum": ["person", "place", "project", "event", "date", "tag"],
                            },
                            "relation": {
                                "type": "string",
                                "enum": ["belongs_to", "located_at", "participated_in", "works_on", "occurred_at", "related_to"],
                            },
                        },
                        "required": ["source", "source_type", "target", "target_type", "relation"],
                    },
                    "description": "Relationships between entities. Only include confident relationships. Can be empty.",
                },
                "risk_level": {
                    "type": "string",
                    "enum": ["auto_safe", "review_first"],
                    "description": "auto_safe if no sensitive info, review_first if contains personal/financial/medical data",
                },
            },
            "required": ["category", "summary", "tags", "entities", "risk_level"],
        },
    },
}


@dataclass
class GemInsight:
    """Core reference data extracted from a single file by Gemma 4.

    GemInsight is the Single Source of Truth (SSoT) for Gemvis:
    - 1:1 mapping: one file → one GemInsight
    - Immutable: file changes trigger new GemInsight generation
    - Local-only: never transmitted externally
    - Restorable: can be regenerated from file at any time

    See docs/GEM_INSIGHT.md for architecture details.
    """
    file_path: str
    category: str = "other"
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=lambda: {
        "people": [], "places": [], "projects": [], "dates": [], "events": []
    })
    relations: list[dict] = field(default_factory=list)
    risk_level: str = "auto_safe"
    error: str | None = None
    file_mtime: float | None = None  # File modification timestamp (Unix epoch)
    file_ctime: float | None = None  # File creation timestamp (Unix epoch)

    # State machine (v2: geminsight-develop)
    analysis_status: AnalysisStatus = "pending"
    last_analyzed_at: str | None = None  # ISO datetime
    added_at: str | None = None          # ISO datetime (when Gemvis first saw the file)
    size_bytes: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "GemInsight":
        """Rehydrate a GemInsight from a dict (e.g. JSON stored in KG as raw_insight).

        Unknown keys are ignored so forward-compat additions don't break loads.
        Missing keys fall back to dataclass defaults.
        """
        valid_keys = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**filtered)


def _get_file_type(path: Path) -> str | None:
    suffix = path.suffix.lower()
    for file_type, extensions in SUPPORTED_EXTENSIONS.items():
        if suffix in extensions:
            return file_type
    return None


def _strip_fences(raw: str) -> str:
    """Remove markdown ```json ... ``` fences if the model added them."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _call_llm_with_tools(file_path: Path, file_type: str, lang: str = "ko") -> dict:
    """Call the LLM with tool calling for structured output.

    Now supports images via Vision API + Tool Calling simultaneously.
    """
    if file_type == "text":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if len(text) > 10000:
            text = text[:10000] + "\n... (truncated)"
        prompt = f"File name: {file_path.name}\n\nContent:\n{text}"

    elif file_type == "document":
        text = extract_pdf_text(file_path)
        prompt = f"File name: {file_path.name}\n(PDF extracted text below)\n\n{text}"

    elif file_type == "image":
        # Use Vision API with Tool Calling for structured output
        prompt = f"File name: {file_path.name}"

    else:
        raise ValueError(f"Unsupported file_type: {file_type}")

    try:
        result = complete_with_tools(
            prompt=prompt,
            tools=[get_analysis_tool(lang)],
            system=get_analysis_prompt(lang),
            tool_choice={"type": "function", "function": {"name": "analyze_file"}},
            image_path=file_path if file_type == "image" else None,
        )

        if not result["tool_calls"]:
            # Tool call이 없으면 이는 심각한 문제 - 로그 상세 기록
            logger.error(
                "Tool call not returned for %s despite tool_choice='required'. "
                "Response content: %s. Falling back to JSON parsing.",
                file_path.name,
                result.get("content", "")[:200]
            )
            return _call_llm_fallback(file_path, file_type, lang)

        # Tool calling 성공 - 명시적 로깅
        tool_call = result["tool_calls"][0]
        logger.info("✓ Tool calling successful for %s (function: %s)", file_path.name, tool_call.function.name)

        arguments = json.loads(tool_call.function.arguments)
        return arguments

    except json.JSONDecodeError as e:
        logger.error("Tool call arguments parsing failed for %s: %s. Falling back.", file_path.name, e)
        return _call_llm_fallback(file_path, file_type, lang)
    except Exception as e:
        logger.error("Tool calling failed for %s: %s. Falling back to text completion.", file_path.name, e)
        return _call_llm_fallback(file_path, file_type, lang)


def _call_llm_fallback(file_path: Path, file_type: str, lang: str = "ko") -> dict:
    """Fallback to free-form JSON text completion when tool calling fails.

    이 함수는 Tool Calling이 실패했을 때만 사용됩니다.
    정상적인 경우 _call_llm_with_tools()가 Tool을 사용합니다.
    """
    logger.warning("⚠ Using fallback JSON parsing for %s (Tool Calling not available)", file_path.name)

    # Fallback 경로에서는 Tool Calling 없이 직접 JSON을 반환하도록 프롬프트 변경
    language = LANG_NAMES.get(lang, "Korean")
    fallback_instructions = (
        f"You are a file analysis assistant. Analyze the given file and return a JSON object with this exact structure:\n"
        f"{{\n"
        f'  "category": "memo|photo|screenshot|document|voice_memo|code|data|other",\n'
        f'  "summary": "one-line summary in {language}",\n'
        f'  "tags": ["tag1", "tag2", "tag3"],  // 3-7 tags in {language}\n'
        f'  "entities": {{\n'
        f'    "people": ["person names"],\n'
        f'    "places": ["place names"],\n'
        f'    "projects": ["project names"],\n'
        f'    "dates": ["date mentions"],\n'
        f'    "events": ["event names"]\n'
        f'  }},\n'
        f'  "relations": [["entity1", "relation", "entity2"]],\n'
        f'  "risk_level": "auto_safe|review_first"\n'
        f"}}\n"
        f"Return ONLY the JSON object, no markdown fences, no extra text."
    )

    if file_type == "text":
        text = file_path.read_text(encoding="utf-8", errors="replace")
        if len(text) > 10000:
            text = text[:10000] + "\n... (truncated)"
        prompt = f"File name: {file_path.name}\n\nContent:\n{text}\n\n{fallback_instructions}"
        raw = complete_text(prompt)

    elif file_type == "image":
        prompt = f"File name: {file_path.name}\n\n{fallback_instructions}"
        try:
            raw = complete_image(file_path, prompt)
        except Exception as e:
            msg = str(e)
            if "Failed to load image" in msg or "400" in msg:
                logger.warning(
                    "Vision call failed (likely no mmproj loaded). "
                    "Falling back to filename-only analysis for %s",
                    file_path.name,
                )
                fallback_prompt = (
                    f"File name: {file_path.name} (image, content unavailable)\n"
                    f"Analyze using only the filename. Set category='photo' or 'screenshot'.\n\n"
                    f"{fallback_instructions}"
                )
                raw = complete_text(fallback_prompt)
            else:
                raise

    elif file_type == "document":
        text = extract_pdf_text(file_path)
        prompt = (
            f"File name: {file_path.name}\n"
            f"(PDF extracted text below)\n\n"
            f"{text}\n\n"
            f"{fallback_instructions}"
        )
        raw = complete_text(prompt)
    else:
        raise ValueError(f"Unsupported file_type: {file_type}")

    # Parse free-form JSON response
    data = json.loads(_strip_fences(raw))
    return data


def generate_insight(file_path: str | Path, lang: str | None = None) -> GemInsight:
    """Generate a GemInsight for the given file using the configured LLM.

    The natural-language fields (summary, tags) are generated in ``lang``.
    When ``lang`` is None, the saved user preference (``preferences.prefs.analyze_lang``)
    is used so the watcher follows whichever language the user picked in the UI.
    """
    from gemvis.preferences import prefs as _prefs
    if lang is None:
        lang = _prefs.analyze_lang

    file_path = Path(file_path)
    insight = GemInsight(file_path=str(file_path))

    if not file_path.exists():
        insight.error = "File not found"
        return insight

    # Capture file timestamps and size (used for calendar date and dashboard sorting)
    try:
        stat = file_path.stat()
        insight.file_mtime = stat.st_mtime
        insight.file_ctime = stat.st_ctime
        insight.size_bytes = stat.st_size
    except Exception as e:
        logger.warning("Failed to get file stats for %s: %s", file_path, e)

    file_type = _get_file_type(file_path)
    if file_type is None:
        insight.error = f"Unsupported file type: {file_path.suffix}"
        insight.analysis_status = "failed"
        return insight

    try:
        data = _call_llm_with_tools(file_path, file_type, lang)
        insight.category = data.get("category", "other")
        insight.summary = data.get("summary", "")
        insight.tags = data.get("tags", [])
        insight.entities = data.get("entities", insight.entities)
        insight.relations = data.get("relations", [])
        insight.risk_level = data.get("risk_level", "auto_safe")
        insight.analysis_status = "completed"
        insight.last_analyzed_at = datetime.now().isoformat()

    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        insight.error = f"JSON parse error: {e}"
        insight.analysis_status = "failed"
    except Exception as e:
        logger.error("Analysis failed for %s: %s", file_path, e)
        insight.error = str(e)
        insight.analysis_status = "failed"

    return insight


# Backward compatibility aliases
AnalysisResult = GemInsight
analyze_file = generate_insight
