"""Parse blog-style HTML (Feishu-compatible subset) into AST for block_converter.

Accepts only safe tags that map to Feishu Docx blocks: h1, h2, h3, p, strong, em,
ul, ol, li, blockquote, hr, pre, code. Output AST matches markdown_parser schema.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


def parse_html_to_ast(html: str) -> list[dict[str, Any]]:
    """Parse simple blog HTML into AST (same schema as parse_markdown_to_ast)."""
    parser = _BlogHTMLParser()
    parser.feed(html.strip())
    return parser.get_ast()


class _BlogHTMLParser(HTMLParser):
    """Parse allowed block/inline tags into AST nodes."""

    def __init__(self) -> None:
        super().__init__()
        self.ast: list[dict[str, Any]] = []
        self._stack: list[tuple[str, list[str], dict[str, Any]]] = []  # (tag, buffer, attrs)
        self._current_text: list[str] = []
        self._list_stack: list[tuple[str, list[str]]] = []  # (ul|ol, items)

    def get_ast(self) -> list[dict[str, Any]]:
        self._flush_text()
        self._flush_list()
        return self.ast

    def _flush_text(self) -> None:
        if self._current_text:
            text = "".join(self._current_text).strip()
            if text:
                self.ast.append({"type": "paragraph", "text": text})
            self._current_text = []

    def _flush_list(self) -> None:
        while self._list_stack:
            tag, items = self._list_stack.pop()
            if items:
                if tag == "ul":
                    self.ast.append({"type": "bullet_list", "items": items})
                else:
                    self.ast.append({"type": "ordered_list", "items": items})

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict((k, v or "") for k, v in attrs)
        if tag in ("h1", "h2", "h3"):
            self._flush_text()
            self._flush_list()
            level = int(tag[1])
            self._stack.append((tag, [], attrs_d))
            return
        if tag in ("ul", "ol"):
            self._flush_text()
            self._list_stack.append((tag, []))
            return
        if tag == "li":
            if self._list_stack:
                self._stack.append((tag, [], attrs_d))
            return
        if tag in ("p", "blockquote"):
            self._flush_text()
            self._flush_list()
            self._stack.append((tag, [], attrs_d))
            return
        if tag == "hr":
            self._flush_text()
            self._flush_list()
            self.ast.append({"type": "hr"})
            return
        if tag in ("pre", "code") and not any(s[0] == "pre" for s in self._stack):
            self._flush_text()
            if tag == "pre":
                self._stack.append((tag, [], attrs_d))
            return
        if tag in ("strong", "b", "em", "i", "code"):
            self._stack.append((tag, [], attrs_d))
            return
        if tag == "br":
            self._current_text.append("\n")
            return

    def handle_endtag(self, tag: str) -> None:
        if tag in ("h1", "h2", "h3"):
            if self._stack and self._stack[-1][0] == tag:
                _, buf, _ = self._stack.pop()
                text = "".join(buf).strip()
                level = int(tag[1])
                self.ast.append({"type": "heading", "level": level, "text": text})
            return
        if tag in ("ul", "ol"):
            self._flush_list()
            return
        if tag == "li":
            if self._stack and self._stack[-1][0] == "li":
                _, buf, _ = self._stack.pop()
                text = "".join(buf).strip()
                if self._list_stack:
                    self._list_stack[-1][1].append(text)
            return
        if tag == "p":
            if self._stack and self._stack[-1][0] == "p":
                _, buf, _ = self._stack.pop()
                text = "".join(buf).strip()
                if text:
                    self.ast.append({"type": "paragraph", "text": text})
            return
        if tag == "blockquote":
            if self._stack and self._stack[-1][0] == "blockquote":
                _, buf, _ = self._stack.pop()
                text = "".join(buf).strip()
                if text:
                    self.ast.append({"type": "blockquote", "text": text})
            return
        if tag == "pre":
            if self._stack and self._stack[-1][0] == "pre":
                _, buf, _ = self._stack.pop()
                code = "".join(buf)
                self.ast.append({"type": "code", "language": "", "text": code})
            return
        if tag in ("strong", "b", "em", "i", "code"):
            if self._stack and self._stack[-1][0] == tag:
                self._stack.pop()
            return

    def handle_data(self, data: str) -> None:
        if self._stack:
            tag = self._stack[-1][0]
            if tag in ("h1", "h2", "h3", "p", "blockquote", "li", "pre"):
                self._stack[-1][1].append(data)
                return
            if tag == "code":
                if len(self._stack) >= 2 and self._stack[-2][0] == "pre":
                    self._stack[-2][1].append(data)
                else:
                    # Inline code: append to parent or current text
                    if len(self._stack) >= 2 and self._stack[-2][0] in ("p", "li", "blockquote", "h1", "h2", "h3"):
                        self._stack[-2][1].append(data)
                    else:
                        self._current_text.append(data)
                return
        self._current_text.append(data)
