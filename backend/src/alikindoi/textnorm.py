"""Normalize job descriptions to clean, consistent markdown.

Sources are inconsistent: JobSpy returns markdown (with escaped characters
like `\\-`), Remotive/The Muse return raw HTML, Adzuna returns plain text.
This module normalizes everything to tidy markdown for uniform rendering.
"""

from __future__ import annotations

import re

_HTML_TAG = re.compile(r"<(p|br|div|li|ul|ol|span|strong|b|em|i|h[1-6]|a)\b[^>]*>", re.I)
_MARKDOWN_ESCAPES = re.compile(r"\\([\-_*\[\]#>|+.!(){}])")
_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_SPACES = re.compile(r"[ \t]+\n")
_BULLET_ARTIFACTS = re.compile(r"^\s*[*+•]\s*(?=[*+•]\s)", re.M)


def looks_like_html(text: str) -> bool:
    return bool(_HTML_TAG.search(text))


def normalize_description(text: str | None) -> str | None:
    """Return a clean markdown version of a raw description."""
    if not text:
        return text

    if looks_like_html(text):
        from markdownify import markdownify

        text = markdownify(
            text,
            heading_style="ATX",
            bullets="-",
            strip=["img", "script", "style"],
        )

    # Undo markdown escaping artifacts (JobSpy escapes -, _, *, ...)
    text = _MARKDOWN_ESCAPES.sub(r"\1", text)
    # Tidy whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_SPACES.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    text = _BULLET_ARTIFACTS.sub("", text)
    return text.strip()
