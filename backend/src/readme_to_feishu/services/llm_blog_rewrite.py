"""LLM service: rewrite README markdown as blog-style HTML (Feishu-compatible subset)."""

from __future__ import annotations

from ..config import OPENAI_API_KEY, LLM_MODEL

BLOG_HTML_SYSTEM = """You are a technical writer. Convert the given README markdown into a clean, blog-style HTML article.

Rules:
- Output ONLY the HTML fragment (no markdown, no explanation). Use only these tags so the result can be imported into Feishu: h1, h2, h3, p, strong, em, ul, ol, li, blockquote, hr, pre, code.
- Do NOT use: div, span, section, article, a, img, table (unless you represent tables as lists or paragraphs).
- Keep the same structure and information; improve readability with short paragraphs and clear headings.
- Use <h1> for the main title once, <h2>/<h3> for sections, <p> for paragraphs, <ul>/<ol>/<li> for lists, <blockquote> for callouts, <hr> for separators, <pre><code> for code blocks.
- Escape any raw < or > in code/content as &lt; and &gt; where needed.
- Output UTF-8; keep Chinese or other languages as-is.
"""


def rewrite_readme_to_blog_html(markdown: str, *, api_key: str | None = None, model: str | None = None) -> str:
    """Call OpenAI to rewrite README as blog-style HTML. Returns HTML string."""
    key = (api_key or "").strip() or OPENAI_API_KEY
    if not key:
        raise ValueError("OPENAI_API_KEY is not set; cannot run LLM blog rewrite")
    model = (model or "").strip() or LLM_MODEL

    from openai import OpenAI
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": BLOG_HTML_SYSTEM},
            {"role": "user", "content": markdown},
        ],
        temperature=0.3,
    )
    content = (response.choices[0].message.content or "").strip()
    # Strip optional markdown code fence if model wrapped HTML in ```html ... ```
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content
