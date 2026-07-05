#!/usr/bin/env python3
import re
import sys


# Remove common JavaScript execution vectors while preserving the original
# HTML formatting and byte layout everywhere else.
EVENT_HANDLER_RE = re.compile(r'(?i)(\s+on[a-z0-9_-]+\s*=\s*)("[^"]*"|\'[^\']*\'|[^\s>]+)')
JS_URI_RE = re.compile(r'(?i)(\s+(?:href|src|xlink:href|formaction|action)\s*=\s*)("(?:javascript|vbscript):[^"]*"|\'(?:javascript|vbscript):[^\']*\'|(?:javascript|vbscript):[^\s>]+)')
SCRIPT_BLOCK_RE = re.compile(r'(?is)<script\b[^>]*>.*?</script\s*>')
SCRIPT_SELF_CLOSING_RE = re.compile(r'(?is)<script\b[^>]*?/\s*>')


def sanitize_html(text: str) -> str:
    # Remove script elements entirely.
    text = SCRIPT_BLOCK_RE.sub('', text)
    text = SCRIPT_SELF_CLOSING_RE.sub('', text)

    # Remove inline event handlers and javascript/vbscript URLs, preserving
    # all other bytes and spacing exactly.
    text = EVENT_HANDLER_RE.sub(r'\1', text)
    text = JS_URI_RE.sub(r'\1#', text)
    return text


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8', errors='surrogateescape') as f:
        original = f.read()

    sanitized = sanitize_html(original)

    if sanitized != original:
        with open(path, 'w', encoding='utf-8', errors='surrogateescape') as f:
            f.write(sanitized)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
