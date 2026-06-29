"""OpenAI-compatible LLM client wrapper for Gemvis.

Works with llama-server, vLLM, and any other OpenAI-compatible endpoint.
"""

import base64
import logging
from pathlib import Path

from openai import OpenAI

from gemvis.config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
from gemvis.preferences import prefs

logger = logging.getLogger(__name__)


def _client() -> OpenAI:
    """Build an OpenAI client pointed at the configured endpoint."""
    return OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)


def complete_text(prompt: str, *, system: str | None = None, temperature: float | None = None) -> str:
    """Single-turn text completion. Returns the raw response text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature if temperature is not None else prefs.llm_temperature,
        max_tokens=prefs.llm_max_tokens,
        top_p=prefs.llm_top_p,
    )
    return (resp.choices[0].message.content or "").strip()


def complete_image(image_path: str | Path, prompt: str, *, temperature: float | None = None) -> str:
    """Single-turn image + text completion (multimodal)."""
    p = Path(image_path)
    suffix = p.suffix.lower()
    mime_map = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
    }
    mime = mime_map.get(suffix, "image/png")
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=temperature if temperature is not None else prefs.llm_temperature,
        max_tokens=prefs.llm_max_tokens,
        top_p=prefs.llm_top_p,
    )
    return (resp.choices[0].message.content or "").strip()


def extract_pdf_text(pdf_path: str | Path, max_chars: int = 10000) -> str:
    """Extract text from a PDF file (server-side; local LLMs can't read PDF bytes directly)."""
    from pypdf import PdfReader
    reader = PdfReader(str(pdf_path))
    chunks = []
    total = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as e:
            logger.warning("PDF page extraction failed: %s", e)
            continue
        chunks.append(text)
        total += len(text)
        if total > max_chars:
            break
    joined = "\n".join(chunks)
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n... (truncated)"
    return joined


def complete_with_tools(
    prompt: str,
    tools: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.1,
    tool_choice: dict | str = "auto",
    image_path: str | Path | None = None,
) -> dict:
    """Single-turn completion with tool calling support.

    Args:
        prompt: User message (text)
        tools: OpenAI tool definitions (function calling schema)
        system: Optional system message
        temperature: Sampling temperature
        tool_choice: "auto", "none", or {"type": "function", "function": {"name": "..."}}
        image_path: Optional image file for Vision API + Tool Calling

    Returns:
        {
            "content": str | None,  # Regular text response
            "tool_calls": [...]     # Tool calls if any
        }
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    # Build user message content (text or multimodal)
    if image_path:
        import base64
        p = Path(image_path)
        suffix = p.suffix.lower()
        mime_map = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp",
        }
        mime = mime_map.get(suffix, "image/png")
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"

        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    else:
        user_content = prompt

    messages.append({"role": "user", "content": user_content})

    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        max_tokens=prefs.llm_max_tokens,
        top_p=prefs.llm_top_p,
    )

    choice = resp.choices[0]
    return {
        "content": choice.message.content,
        "tool_calls": choice.message.tool_calls or [],
    }


def stream_chat(
    messages: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.7,
):
    """Streaming multi-turn chat. Yields text chunks as they arrive from the LLM."""
    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    stream = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=all_messages,
        temperature=temperature,
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def complete_chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.1,
    tool_choice: str = "auto",
) -> dict:
    """Multi-turn conversation with tool calling support.

    Returns:
        {"content": str | None, "tool_calls": list}
    """
    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=all_messages,
        tools=tools,
        tool_choice=tool_choice,
        temperature=temperature,
        max_tokens=prefs.llm_max_tokens,
        top_p=prefs.llm_top_p,
    )
    choice = resp.choices[0]
    return {
        "content": choice.message.content,
        "tool_calls": choice.message.tool_calls or [],
    }


def complete_chat(
    messages: list[dict],
    *,
    system: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Multi-turn conversation with full message history.

    Args:
        messages: Conversation history as [{"role": "user"|"assistant", "content": str}, ...]
        system: Optional system prompt
        temperature: Sampling temperature (default 0.7 for natural conversation)
    """
    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    resp = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=all_messages,
        temperature=temperature,
        max_tokens=prefs.llm_max_tokens,
        top_p=prefs.llm_top_p,
    )
    return (resp.choices[0].message.content or "").strip()


def check_health() -> bool:
    """Light-weight health probe — returns True if the endpoint is reachable."""
    try:
        resp = _client().chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return bool(resp.choices)
    except Exception as e:
        logger.warning("LLM health check failed: %s", e)
        return False
