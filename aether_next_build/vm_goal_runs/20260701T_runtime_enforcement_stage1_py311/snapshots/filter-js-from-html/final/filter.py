#!/usr/bin/env python3
"""In-place HTML JavaScript remover.

This script performs conservative text-based sanitization intended to preserve
HTML formatting and benign content as much as possible while removing common
JavaScript/XSS vectors:
- <script>...</script> blocks
- inline event handler attributes (onclick, onload, etc.)
- javascript: URLs in common URL-bearing attributes
- a few additional script-bearing attributes such as srcdoc and style
  expressions, handled minimally in-place.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SCRIPT_BLOCK_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)
EVENT_ATTR_RE = re.compile(
    r'''\s+on[a-zA-Z][a-zA-Z0-9_-]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',
    re.IGNORECASE,
)
JS_URL_ATTR_RE = re.compile(
    r'''(\b(?:href|src|xlink:href|formaction|action|poster)\s*=\s*)("|')\s*javascript\s*:[^"']*\2''',
    re.IGNORECASE,
)
JS_URL_ATTR_UNQUOTED_RE = re.compile(
    r'''(\b(?:href|src|xlink:href|formaction|action|poster)\s*=\s*)(javascript\s*:[^\s>]+)''',
    re.IGNORECASE,
)
STYLE_EXPR_RE = re.compile(r'''(\bstyle\s*=\s*)("|')(.*?)\2''', re.IGNORECASE | re.DOTALL)
SRCDOC_RE = re.compile(r'''\s+srcdoc\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''', re.IGNORECASE | re.DOTALL)


def sanitize_html(text: str) -> str:
    text = SCRIPT_BLOCK_RE.sub("", text)
    text = EVENT_ATTR_RE.sub("", text)
    text = SRCDOC_RE.sub("", text)

    def _strip_js_url(match: re.Match[str]) -> str:
        prefix, quote = match.group(1), match.group(2)
        return f"{prefix}{quote}{quote}"

    text = JS_URL_ATTR_RE.sub(_strip_js_url, text)

    def _strip_js_url_unquoted(match: re.Match[str]) -> str:
        prefix = match.group(1)
        return f"{prefix}''"

    text = JS_URL_ATTR_UNQUOTED_RE.sub(_strip_js_url_unquoted, text)

    def _sanitize_style(match: re.Match[str]) -> str:
        prefix, quote, value = match.group(1), match.group(2), match.group(3)
        cleaned = re.sub(r'expression\s*\([^)]*\)', '', value, flags=re.IGNORECASE)
        cleaned = re.sub(r'url\s*\(\s*["\']?\s*javascript\s*:[^)]*\)', 'url()', cleaned, flags=re.IGNORECASE)
        return f"{prefix}{quote}{cleaned}{quote}"

    text = STYLE_EXPR_RE.sub(_sanitize_style, text)
    return text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {Path(argv[0]).name} <html-file>", file=sys.stderr)
        return 2

    path = Path(argv[1])
    data = path.read_text(encoding="utf-8", errors="surrogatepass")
    cleaned = sanitize_html(data)
    if cleaned != data:
        path.write_text(cleaned, encoding="utf-8", errors="surrogatepass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
