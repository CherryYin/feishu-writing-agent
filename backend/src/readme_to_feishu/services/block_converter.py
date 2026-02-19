"""Markdown AST → Feishu Docx blocks conversion - Architecture 3.3.

This module builds **Feishu Docx API-compatible** block payloads for
`POST /open-apis/docx/v1/documents/{document_id}/blocks/{block_id}/children`.

Important: the Docx schema uses `text_run.content` (not `text_run.text`).
"""

from __future__ import annotations

from typing import Any

def build_feishu_blocks_schema(ast: list[dict[str, Any]], filters: set[str] | None = None) -> list[dict[str, Any]]:
    """Build blocks in Feishu Docx API format.

    Block types (Docx, server API):
    - 2: text
    - 3/4/5: heading1/heading2/heading3
    - 9: code (disabled by default; see notes)
    - 10: divider

    Notes:
    - Lists/quotes are emitted as normal text blocks for maximum compatibility.
      (Native list blocks require additional structure/children semantics.)
    - Code blocks are emitted as *text blocks* (not block_type=9) by default because
      Feishu's Docx "code" block schema is strict (language enums, element schema),
      and invalid params will cause publishing to fail. Once the exact schema is
      confirmed, you can re-enable native code blocks.
    """
    filters = filters or set()
    result: list[dict[str, Any]] = []
    for node in ast:
        if _skip_node(node, filters):
            continue
        result.extend(_feishu_blocks_for_node(node))
    return result


def _skip_node(node: dict[str, Any], filters: set[str]) -> bool:
    if "badge" in filters and node.get("type") == "paragraph":
        text = (node.get("text") or "").strip()
        if "![ " in text or "](https://" in text and "badge" in text.lower():
            return True
    if "ci_status" in filters and node.get("type") == "paragraph":
        text = (node.get("text") or "").strip().lower()
        if "travis" in text or "github actions" in text or "ci" in text:
            return True
    return False


def _text_elements(text: str) -> dict[str, Any]:
    """Docx text elements payload."""
    return {"elements": [{"text_run": {"content": text or ""}}]}


def _feishu_text_block(text: str) -> dict[str, Any]:
    return {"block_type": 2, "text": _text_elements(text)}


def _feishu_heading_block(level: int, text: str) -> dict[str, Any]:
    level = 1 if level < 1 else 3 if level > 3 else level
    key = ["heading1", "heading2", "heading3"][level - 1]
    return {"block_type": level + 2, key: _text_elements(text)}


def _feishu_code_block(language: str, code: str) -> dict[str, Any]:
    return {
        "block_type": 9,
        "code": {
            "language": language or "",
            "elements": [{"text_run": {"content": code or ""}}],
        },
    }


def _feishu_divider_block() -> dict[str, Any]:
    return {"block_type": 10, "divider": {}}


def _feishu_blocks_for_node(node: dict[str, Any]) -> list[dict[str, Any]]:
    t = node.get("type")
    if t == "heading":
        return [_feishu_heading_block(int(node.get("level", 1)), str(node.get("text", "")))]
    if t == "paragraph":
        return [_feishu_text_block(str(node.get("text", "")))]
    if t == "code":
        # Safer fallback: emit as normal text blocks to avoid Feishu invalid-param errors.
        lang = str(node.get("language", "") or "").strip()
        header = f"```{lang}".rstrip()
        code = str(node.get("text", "") or "")
        footer = "```"
        text = f"{header}\n{code}\n{footer}"
        return _chunk_text_to_blocks(text)
    if t == "hr":
        return [_feishu_divider_block()]
    if t == "blockquote":
        # Native callout schema is more complex; emit as plain text for compatibility.
        return [_feishu_text_block("> " + str(node.get("text", "")))]
    if t == "bullet_list":
        items = node.get("items", []) or []
        return [_feishu_text_block("• " + str(it)) for it in items]
    if t == "ordered_list":
        items = node.get("items", []) or []
        blocks: list[dict[str, Any]] = []
        for idx, it in enumerate(items, start=1):
            blocks.append(_feishu_text_block(f"{idx}. {it}"))
        return blocks
    return []


def _chunk_text_to_blocks(text: str, max_chars: int = 5000) -> list[dict[str, Any]]:
    """Split long text into multiple text blocks to satisfy API limits."""
    if len(text) <= max_chars:
        return [_feishu_text_block(text)]
    blocks: list[dict[str, Any]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        blocks.append(_feishu_text_block(text[start:end]))
        start = end
    return blocks
