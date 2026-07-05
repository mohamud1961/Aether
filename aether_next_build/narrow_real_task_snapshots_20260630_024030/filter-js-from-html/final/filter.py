#!/usr/bin/env python3
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")
TAG_RE = re.compile(r"(?s)<[^>]*>")
SCRIPT_TAG_RE = re.compile(r"(?is)<script\b")
ATTR_RE = re.compile(
    r'''(?is)
    (\s+)
    ([^\s=<>'"/]+)
    (?:\s*=\s*
        (?:
            "([^"]*)"
          | '([^']*)'
          | ([^\s"'=<>`]+)
        )
    )?
    '''
)

URL_ATTRS = {
    "action",
    "background",
    "cite",
    "data",
    "formaction",
    "href",
    "poster",
    "src",
    "xlink:href",
}


def _normalize_for_scheme(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"[\x00-\x20]+", "", value)
    return value.lower()


def _dangerous_url(value: str) -> bool:
    normalized = _normalize_for_scheme(value)
    return normalized.startswith("javascript:") or normalized.startswith("vbscript:")


def sanitize_tag(tag: str) -> str:
    if len(tag) < 2:
        return tag

    if tag.startswith("</") or tag.startswith("<!") or tag.startswith("<?"):
        return tag

    if SCRIPT_TAG_RE.match(tag):
        return ""

    def repl(match: re.Match[str]) -> str:
        name = match.group(2).lower()
        raw_value = match.group(3) or match.group(4) or match.group(5) or ""

        if name.startswith("on"):
            return ""
        if name == "srcdoc":
            return ""
        if name in URL_ATTRS and raw_value and _dangerous_url(raw_value):
            return ""
        if name == "style":
            normalized = _normalize_for_scheme(raw_value)
            if "expression(" in normalized or "url(javascript:" in normalized or "url(vbscript:" in normalized:
                return ""
        return match.group(0)

    return ATTR_RE.sub(repl, tag)


def sanitize_html(content: str) -> str:
    content = SCRIPT_BLOCK_RE.sub("", content)
    return TAG_RE.sub(sanitize_tag, content)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: filter.py <html_file>", file=sys.stderr)
        return 1

    path = Path(argv[1])
    with path.open("r", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        content = handle.read()

    sanitized = sanitize_html(content)

    with path.open("w", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        handle.write(sanitized)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
