#!/usr/bin/env python3
"""In-place HTML sanitizer that removes JavaScript-bearing constructs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")
EVENT_ATTR_RE = re.compile(r'''(?is)\s+on[a-z0-9_-]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+)''')
SRCDOC_ATTR_RE = re.compile(r'''(?is)\s+srcdoc\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>`]+)''')
JS_URI_ATTR_RE = re.compile(
    r'''(?is)\s+(?:href|src|action|formaction|xlink:href|poster|background)\s*=\s*(?:"\s*(?:javascript|vbscript)\s*:[^"]*"|'\s*(?:javascript|vbscript)\s*:[^']*'|(?:javascript|vbscript)\s*:[^\s"'=<>`]+)'''
)
STYLE_ATTR_RE = re.compile(r'''(?is)(\s+style\s*=\s*)(["'])(.*?)\2''')
DANGEROUS_STYLE_RE = re.compile(r'''(?is)expression\s*\([^)]*\)|url\s*\(\s*(['"]?)\s*(?:javascript|vbscript)\s*:[^)]*\)''')


def _sanitize_style(match: re.Match[str]) -> str:
    prefix, quote, value = match.groups()
    cleaned = DANGEROUS_STYLE_RE.sub("", value)
    if not cleaned.strip():
        return ""
    return f"{prefix}{quote}{cleaned}{quote}"


def sanitize_html(html: str) -> str:
    html = SCRIPT_RE.sub("", html)
    html = EVENT_ATTR_RE.sub("", html)
    html = SRCDOC_ATTR_RE.sub("", html)
    html = JS_URI_ATTR_RE.sub("", html)
    html = STYLE_ATTR_RE.sub(_sanitize_style, html)
    return html


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: filter.py <html-file>")

    path = Path(sys.argv[1])
    html = path.read_text(encoding="utf-8")
    sanitized = sanitize_html(html)
    if sanitized != html:
        path.write_text(sanitized, encoding="utf-8")


if __name__ == "__main__":
    main()
