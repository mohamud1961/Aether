#!/usr/bin/env python3
import re
import sys
from pathlib import Path

SCRIPT_RE = re.compile(r'(?is)<script\b.*?</script\s*>')
EVENT_ATTR_RE = re.compile(r'\s+on[a-zA-Z0-9_-]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)')
JS_URI_RE = re.compile(r'(?i)(\s+(?:href|src|xlink:href|formaction|action|poster)\s*=\s*)("|\')?\s*javascript:[^\s>"\']*(\2)?')
STYLE_EXPR_RE = re.compile(r'(?is)expression\s*\([^)]*\)')
STYLE_JS_URL_RE = re.compile(r'(?is)url\s*\(\s*["\']?\s*javascript:[^)]*\)')


def sanitize(html: str) -> str:
    html = SCRIPT_RE.sub('', html)
    html = EVENT_ATTR_RE.sub('', html)
    html = JS_URI_RE.sub(r'\1#', html)
    html = STYLE_EXPR_RE.sub('', html)
    html = STYLE_JS_URL_RE.sub('url()', html)
    return html


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    path = Path(sys.argv[1])
    data = path.read_text(encoding='utf-8', errors='surrogateescape')
    cleaned = sanitize(data)
    if cleaned != data:
        path.write_text(cleaned, encoding='utf-8', errors='surrogateescape')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
