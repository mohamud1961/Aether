#!/usr/bin/env python3
"""In-place HTML JavaScript remover.

Usage: filter.py argv[1]
Removes harmful JavaScript while preserving HTML structure and formatting.
Performs in-place sanitization.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path


_DANGEROUS_ATTRS = {
    "src", "href", "action", "formaction", "xlink:href", "poster", "data"
}


def _clean_style(value: str) -> str:
    # Remove javascript: and expression() without reformatting unrelated CSS.
    value = re.sub(r"(?is)\\bexpression\\s*\\([^)]*\\)", "", value)
    value = re.sub(r"(?is)javascript\\s*:", "", value)
    return value


class Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.out = []
        self.skip_script = 0
        self.skip_tag = None

    def _emit_start(self, tag: str, attrs: list[tuple[str, str | None]], closing: str) -> None:
        parts = ["<", tag]
        for name, value in attrs:
            lname = name.lower()
            if lname.startswith("on"):
                continue
            if lname in _DANGEROUS_ATTRS and value is not None and re.match(r"(?is)\\s*javascript\\s*:", value):
                continue
            if lname == "style" and value is not None:
                value = _clean_style(value)
            parts.append(" ")
            parts.append(name)
            if value is not None:
                parts.append("=\"")
                parts.append(value)
                parts.append('"')
        parts.append(closing)
        self.out.append("".join(parts))

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "script":
            self.skip_script += 1
            return
        self._emit_start(tag, attrs, ">")

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "script":
            return
        self._emit_start(tag, attrs, " />")

    def handle_endtag(self, tag):
        if tag.lower() == "script":
            if self.skip_script:
                self.skip_script -= 1
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip_script:
            self.out.append(data)

    def handle_comment(self, data):
        if not self.skip_script:
            self.out.append(f"<!--{data}-->")

    def handle_entityref(self, name):
        if not self.skip_script:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip_script:
            self.out.append(f"&#{name};")

    def handle_decl(self, decl):
        if not self.skip_script:
            self.out.append(f"<!{decl}>")

    def unknown_decl(self, data):
        if not self.skip_script:
            self.out.append(f"<![{data}]>")


def sanitize_html(text: str) -> str:
    parser = Sanitizer()
    parser.feed(text)
    parser.close()
    return "".join(parser.out)


def main() -> int:
    if len(sys.argv) < 2:
        return 1
    path = Path(sys.argv[1])
    original = path.read_text(encoding="utf-8", errors="replace")
    cleaned = sanitize_html(original)
    path.write_text(cleaned, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
