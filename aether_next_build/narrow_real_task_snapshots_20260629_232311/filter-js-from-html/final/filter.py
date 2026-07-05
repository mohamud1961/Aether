#!/usr/bin/env python3
"""In-place HTML sanitizer that removes common JavaScript execution vectors.

The script intentionally avoids HTML reserialization so that formatting and
benign content are preserved as closely as possible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b[^>]*>.*?</script\s*>")
SCRIPT_SELF_CLOSING_RE = re.compile(r"(?is)<script\b[^>]*?/\s*>")
EVENT_HANDLER_RE = re.compile(
    r'''(?is)\s+on[a-z0-9_:-]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)'''
)
JS_URL_RE = re.compile(
    r'''(?is)(\s+(?:href|src|action|formaction|xlink:href|poster|data)\s*=\s*)("|')\s*javascript\s*:[^"']*(\2)|'''
    r'''(\s+(?:href|src|action|formaction|xlink:href|poster|data)\s*=\s*)([^\s>]+)'''
)


def sanitize_html(text: str) -> str:
    """Remove script blocks and obvious JavaScript-bearing attributes."""
    text = SCRIPT_BLOCK_RE.sub("", text)
    text = SCRIPT_SELF_CLOSING_RE.sub("", text)
    text = EVENT_HANDLER_RE.sub("", text)

    def repl(match: re.Match[str]) -> str:
        quoted_prefix = match.group(1)
        quote = match.group(2)
        quoted_value = match.group(3)
        bare_prefix = match.group(4)
        bare_value = match.group(5)

        if quoted_prefix is not None:
            return "" if quoted_value is not None and re.match(r"(?is)^\s*javascript\s*:", quoted_value or "") else match.group(0)
        if bare_prefix is not None:
            return "" if re.match(r"(?is)^javascript\s*:", bare_value or "") else match.group(0)
        return match.group(0)

    # Remove javascript: URLs while leaving other attributes untouched.
    def url_repl(match: re.Match[str]) -> str:
        if match.group(1) is not None:
            if re.match(r"(?is)^\s*javascript\s*:", match.group(3) or ""):
                return ""
            return match.group(0)
        if match.group(4) is not None:
            if re.match(r"(?is)^javascript\s*:", match.group(5) or ""):
                return ""
            return match.group(0)
        return match.group(0)

    text = JS_URL_RE.sub(url_repl, text)
    return text


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: filter.py <html-file>")

    path = Path(sys.argv[1])
    original = path.read_text(encoding="utf-8")
    sanitized = sanitize_html(original)
    if sanitized != original:
        path.write_text(sanitized, encoding="utf-8")


if __name__ == "__main__":
    main()
