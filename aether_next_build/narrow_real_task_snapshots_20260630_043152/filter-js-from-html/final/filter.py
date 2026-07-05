#!/usr/bin/env python3
import re
import sys
from pathlib import Path

# Remove <script> blocks entirely, preserving all non-script HTML unchanged.
SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.IGNORECASE | re.DOTALL)

# Remove inline event handler attributes such as onclick=..., onload=..., etc.
EVENT_HANDLER_RE = re.compile(
    r"\s+on[a-zA-Z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE,
)

# Remove javascript: URLs from common URL-bearing attributes.
URL_ATTRS = r"(?:href|src|action|formaction|poster|xlink:href)"
JS_URL_QUOTED_RE = re.compile(
    rf"(\b{URL_ATTRS}\s*=\s*)(\"|')\s*javascript:[\s\S]*?(\2)",
    re.IGNORECASE,
)
JS_URL_UNQUOTED_RE = re.compile(
    rf"(\b{URL_ATTRS}\s*=\s*)javascript:[^\s>]*",
    re.IGNORECASE,
)

# Remove inline style expressions that execute script in legacy browsers.
STYLE_EXPR_RE = re.compile(
    r"(\bstyle\s*=\s*)(\"|')[\s\S]*?expression\s*\([^\"]*?(\2)",
    re.IGNORECASE,
)
STYLE_JS_URL_RE = re.compile(
    r"(\bstyle\s*=\s*)(\"|')[\s\S]*?javascript:[\s\S]*?(\2)",
    re.IGNORECASE,
)


def remove_javascript(html: str) -> str:
    html = SCRIPT_RE.sub("", html)
    html = EVENT_HANDLER_RE.sub("", html)
    html = JS_URL_QUOTED_RE.sub(r"\1\3", html)
    html = JS_URL_UNQUOTED_RE.sub(r"\1#", html)
    html = STYLE_EXPR_RE.sub(r"\1\2\2", html)
    html = STYLE_JS_URL_RE.sub(r"\1\2\2", html)
    return html


def main() -> int:
    if len(sys.argv) != 2:
        return 1

    path = Path(sys.argv[1])
    html = path.read_text(encoding="utf-8", errors="surrogateescape")
    cleaned = remove_javascript(html)
    path.write_text(cleaned, encoding="utf-8", errors="surrogateescape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
