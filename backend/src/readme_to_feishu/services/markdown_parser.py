"""Markdown parsing to AST - Architecture 3.2 (structured parse).

This is a small, line-based block parser intended for MVP publishing.
For full GFM fidelity (tables, nested lists, images), swap in a real Markdown AST
parser later (mistune/remark/etc.).
"""

from __future__ import annotations

from typing import Any

# Simple line-based block parser producing AST (list of block dicts).
# For full GFM (tables, etc.) consider mistune or remark.


def parse_markdown_to_ast(markdown: str) -> list[dict[str, Any]]:
    """
    Parse markdown into a simple AST: list of block dicts.
    Each block: { "type": "heading"|"paragraph"|"code"|"list"|"blockquote"|"table"|"image"|"hr", ... }
    """
    ast: list[dict[str, Any]] = []
    _parse_blocks(markdown, ast)
    return ast


def _parse_blocks(text: str, out: list[dict[str, Any]]) -> None:
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # Heading
        if stripped.startswith("#"):
            level = 0
            for c in stripped:
                if c == "#":
                    level += 1
                else:
                    break
            if level <= 3:
                content = stripped[level:].strip()
                out.append({"type": "heading", "level": level, "text": content})
            i += 1
            continue
        # Code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or ""
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            out.append({"type": "code", "language": lang, "text": "\n".join(code_lines)})
            continue
        # Blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            out.append({"type": "blockquote", "text": "\n".join(quote_lines)})
            continue
        # HR
        if stripped in ("---", "***", "___"):
            out.append({"type": "hr"})
            i += 1
            continue
        # Unordered list
        if stripped.startswith("- ") or stripped.startswith("* "):
            items = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                items.append(lines[i].strip()[2:].strip())
                i += 1
            out.append({"type": "bullet_list", "items": items})
            continue
        # Ordered list
        if len(stripped) >= 2 and stripped[0].isdigit() and stripped[1:2] in (".", ")"):
            items = []
            while i < len(lines):
                s = lines[i].strip()
                if len(s) >= 2 and s[0].isdigit() and s[1:2] in (".", ")"):
                    idx = 2
                    while idx < len(s) and s[idx].isdigit():
                        idx += 1
                    if idx < len(s) and s[idx : idx + 1] in (".", ")"):
                        items.append(s[idx + 1 :].strip())
                    else:
                        items.append(s[2:].strip())
                    i += 1
                else:
                    break
            out.append({"type": "ordered_list", "items": items})
            continue
        # Paragraph (collect until blank or another block)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            out.append({"type": "paragraph", "text": "\n".join(para_lines)})
    return


def _is_block_start(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.startswith("#"):
        return True
    if s.startswith("```"):
        return True
    if s.startswith(">"):
        return True
    if s in ("---", "***", "___"):
        return True
    if s.startswith("- ") or s.startswith("* "):
        return True
    if len(s) >= 2 and s[0].isdigit() and s[1:2] in (".", ")"):
        return True
    return False
