#!/usr/bin/env python3
import html
import re
import sys
from pathlib import Path

SCRIPT_BLOCK_RE = re.compile(r"(?is)<script\b[^>]*>.*?(?:</script\s*>|$)")
TAG_NAME_RE = re.compile(r"^\s*([^\s/>!]+)(.*)$", re.S)
ATTR_RE = re.compile(r"\s+([^\s=/<>`]+)(\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s\"'=<>`]+)))?", re.S)

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


def _find_tag_end(text: str, start: int) -> int:
    quote = ""
    i = start + 1
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        else:
            if ch == '"' or ch == "'":
                quote = ch
            elif ch == ">":
                return i
        i += 1
    return -1


def _dangerous_url(value: str) -> bool:
    normalized = html.unescape(value).strip().lower()
    return normalized.startswith("javascript:")


def _sanitize_start_tag(tag: str) -> str:
    if len(tag) < 3 or tag[0] != "<" or tag[1] in "/!?":
        return tag

    inner = tag[1:-1]
    m = TAG_NAME_RE.match(inner)
    if not m:
        return tag

    tag_name = m.group(1).lower()
    rest_offset = m.start(2)
    rest = m.group(2)

    removals = []
    attrs = []
    for am in ATTR_RE.finditer(rest):
        name = am.group(1).lower()
        raw_value = am.group(3)
        if raw_value is None:
            raw_value = am.group(4)
        if raw_value is None:
            raw_value = am.group(5)

        dangerous = False
        if name.startswith("on"):
            dangerous = True
        elif name == "srcdoc":
            dangerous = True
        elif name == "style" and raw_value is not None:
            style_val = html.unescape(raw_value).lower()
            dangerous = ("javascript:" in style_val) or ("expression(" in style_val)
        elif name in URL_ATTRS and raw_value is not None:
            dangerous = _dangerous_url(raw_value)

        attrs.append((name, raw_value, am))
        if dangerous:
            removals.append((rest_offset + am.start(), rest_offset + am.end()))

    if tag_name == "meta":
        http_equiv_refresh = False
        content_match = None
        for name, raw_value, am in attrs:
            if name == "http-equiv" and raw_value is not None:
                if html.unescape(raw_value).strip().lower() == "refresh":
                    http_equiv_refresh = True
            elif name == "content":
                content_match = (raw_value, am)
        if http_equiv_refresh and content_match is not None:
            raw_value, am = content_match
            if raw_value is not None and _dangerous_url(raw_value):
                removals.append((rest_offset + am.start(), rest_offset + am.end()))
            elif raw_value is not None:
                content_val = html.unescape(raw_value).strip().lower()
                if "javascript:" in content_val:
                    removals.append((rest_offset + am.start(), rest_offset + am.end()))

    if not removals:
        return tag

    removals.sort()
    merged = []
    for start, end in removals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    pieces = []
    cursor = 0
    for start, end in merged:
        pieces.append(inner[cursor:start])
        cursor = end
    pieces.append(inner[cursor:])
    return "<" + "".join(pieces) + ">"


def sanitize_html(text: str) -> str:
    text = SCRIPT_BLOCK_RE.sub("", text)
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch != "<":
            out.append(ch)
            i += 1
            continue
        end = _find_tag_end(text, i)
        if end == -1:
            out.append(text[i:])
            break
        tag = text[i : end + 1]
        out.append(_sanitize_start_tag(tag))
        i = end + 1
    return "".join(out)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: filter.py <html-file>", file=sys.stderr)
        return 1

    path = Path(sys.argv[1])
    data = path.read_bytes().decode("latin1")
    cleaned = sanitize_html(data)
    path.write_bytes(cleaned.encode("latin1"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
