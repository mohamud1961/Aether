#!/usr/bin/env python3
import re
import sys
from pathlib import Path

SCRIPT_BLOCK_RE = re.compile(br"(?is)<script\b[^>]*>.*?</script\s*>")
EVENT_ATTR_RE = re.compile(br"(?i)\s+on[a-z0-9_-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)")
SRCDOC_ATTR_RE = re.compile(br"(?i)\s+srcdoc\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)")
JS_URL_PREFIX_RE = re.compile(
    br"(?i)(\b(?:href|src|xlink:href|action|formaction|poster|data|cite|background|lowsrc|dynsrc|codebase|archive)\s*=\s*(?:\"|')?)\s*javascript:"
)


def sanitize_html(data: bytes) -> bytes:
    data = SCRIPT_BLOCK_RE.sub(b"", data)
    data = EVENT_ATTR_RE.sub(b"", data)
    data = SRCDOC_ATTR_RE.sub(b"", data)
    data = JS_URL_PREFIX_RE.sub(br"\1", data)
    return data


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: filter.py <html-file>")

    path = Path(sys.argv[1])
    original = path.read_bytes()
    cleaned = sanitize_html(original)
    if cleaned != original:
        path.write_bytes(cleaned)


if __name__ == "__main__":
    main()
