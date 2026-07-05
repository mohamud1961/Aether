#!/usr/bin/env python3
import re
import sys
from pathlib import Path

SCRIPT_RE = re.compile(r'(?is)<script\b[^>]*>.*?</script\s*>')
ON_ATTR_RE = re.compile(r'''(?is)\s+on[a-z0-9_:-]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''')
JS_URL_RE = re.compile(r'''(?is)(\b(?:href|src|action|formaction|xlink:href)\s*=\s*)(["']?)\s*javascript\s*:(.*?)(\2)''')
STYLE_EXPR_RE = re.compile(r'''(?is)\s+style\s*=\s*("[^"]*expression\s*\([^\"]*\)[^"]*"|'[^']*expression\s*\([^\']*\)[^']*')''')


def _strip_js_urls(html: str) -> str:
    def repl(match: re.Match) -> str:
        prefix = match.group(1)
        quote = match.group(2)
        tail = match.group(3)
        q = quote or ''
        return f"{prefix}{q}{tail.lstrip()}{q}"

    return JS_URL_RE.sub(repl, html)


def sanitize(html: str) -> str:
    html = SCRIPT_RE.sub('', html)
    html = ON_ATTR_RE.sub('', html)
    html = _strip_js_urls(html)
    html = STYLE_EXPR_RE.sub('', html)
    return html


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: filter.py HTML_FILE', file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    try:
        original = path.read_text(encoding='utf-8', errors='surrogateescape')
        filtered = sanitize(original)
        path.write_text(filtered, encoding='utf-8', errors='surrogateescape')
    except OSError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
