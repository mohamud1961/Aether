#!/usr/bin/env python3
"""In-place HTML JavaScript stripper.

This script removes common JavaScript-bearing content from an HTML file while
preserving the rest of the bytes and formatting as much as possible.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SCRIPT_BLOCK_RE = re.compile(br"(?is)<script\b[^>]*>.*?</script\s*>")
EVENT_ATTR_RE = re.compile(
    br"""(?is)\s+on[a-z0-9_-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)"""
)
JS_URL_ATTR_RE = re.compile(
    br"""(?is)\s+(?:href|src|action|formaction|xlink:href|poster|background|data|cite|longdesc|profile|ping|srcset)\s*=\s*(?:"\s*javascript:[^"]*"|'\s*javascript:[^']*'|javascript:[^\s>]+)"""
)


def sanitize_html(data: bytes) -> bytes:
    data = SCRIPT_BLOCK_RE.sub(b"", data)
    data = EVENT_ATTR_RE.sub(b"", data)
    data = JS_URL_ATTR_RE.sub(b"", data)
    return data


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: filter.py HTML_FILE", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    original = path.read_bytes()
    filtered = sanitize_html(original)
    if filtered != original:
        path.write_bytes(filtered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
