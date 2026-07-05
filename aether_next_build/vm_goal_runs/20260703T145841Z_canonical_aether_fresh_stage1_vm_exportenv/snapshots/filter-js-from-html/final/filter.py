#!/usr/bin/env python3
"""Filter JavaScript from an HTML file in place while preserving formatting."""

from __future__ import annotations

import re
import sys
from pathlib import Path


_SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")
_EVENT_ATTR_RE = re.compile(r'(?i)\s+on[a-z0-9_-]+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)')
_JS_URL_RE = re.compile(r'(?i)(\s(?:href|src|action|formaction)\s*=\s*)("|\')\s*javascript:[^"\']*(\2)')
_JS_URL_UNQUOTED_RE = re.compile(r'(?i)(\s(?:href|src|action|formaction)\s*=\s*)javascript:[^\s>]+')
_STYLE_EXPR_RE = re.compile(r'(?is)(\sstyle\s*=\s*)("[^"]*"|\'[^\']*\'|[^\s>]+)')


def _clean_style_value(value: str) -> str:
    lower = value.lower()
    if "expression(" in lower or "javascript:" in lower:
        return "''" if value.startswith("'") or value.endswith("'") else '""'
    return value


def filter_html(text: str) -> str:
    text = _SCRIPT_BLOCK_RE.sub("", text)
    text = _EVENT_ATTR_RE.sub("", text)
    text = _JS_URL_RE.sub(r"\1\2\2", text)
    text = _JS_URL_UNQUOTED_RE.sub(r"\1#", text)

    def _style_repl(match: re.Match[str]) -> str:
        prefix, value = match.group(1), match.group(2)
        cleaned = _clean_style_value(value)
        return prefix + cleaned

    text = _STYLE_EXPR_RE.sub(_style_repl, text)
    return text


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: filter.py <html-file>", file=sys.stderr)
        return 1

    path = Path(argv[1])
    original = path.read_text(encoding="utf-8", errors="surrogateescape")
    filtered = filter_html(original)
    path.write_text(filtered, encoding="utf-8", errors="surrogateescape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
