#!/usr/bin/env python3
"""Fail closed if the public funding site drifts from its canonical evidence story."""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "website" / "public"
HTML_PATH = PUBLIC / "funding-cards.html"
BRIEF_PATH = PUBLIC / "aether-research-brief.md"
ROOT_VERCEL = ROOT / "vercel.json"
NESTED_VERCEL = PUBLIC / "vercel.json"


class FundingSiteError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise FundingSiteError(message)


def _json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - publication gate should explain malformed config
        _fail(f"cannot parse {path.relative_to(ROOT)}: {type(exc).__name__}: {exc}")
    if not isinstance(value, dict):
        _fail(f"expected JSON object: {path.relative_to(ROOT)}")
    return value


class RefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in {"href", "src"} and value:
                self.refs.append((tag, key, value))


def _rewrite_pairs(config: dict[str, object]) -> list[tuple[str, str]]:
    rows = config.get("rewrites")
    if not isinstance(rows, list):
        _fail("vercel rewrites must be a list")
    pairs: list[tuple[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            _fail("vercel rewrite row must be an object")
        source = str(row.get("source") or "")
        destination = str(row.get("destination") or "")
        if not source.startswith("/") or not destination.startswith("/"):
            _fail(f"invalid rewrite: {row!r}")
        pairs.append((source, destination))
    return pairs


def _require_markers(text: str, markers: tuple[str, ...], *, label: str) -> int:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        _fail(f"{label} missing required proof/caveat markers: {missing}")
    return len(markers)


def main() -> int:
    required_files = (
        PUBLIC / "funding-cards.html",
        PUBLIC / "aether-funding-cards.css",
        PUBLIC / "aether-funding-cards.js",
        PUBLIC / "aether-research-brief.md",
        PUBLIC / "vercel.json",
        ROOT_VERCEL,
    )
    for path in required_files:
        if not path.is_file():
            _fail(f"missing funding-site file: {path.relative_to(ROOT)}")

    root_config = _json(ROOT_VERCEL)
    nested_config = _json(NESTED_VERCEL)
    if root_config.get("framework", "__missing__") is not None:
        _fail("root Vercel config must explicitly use framework=null for the static funding site")
    if root_config.get("outputDirectory") != "website/public":
        _fail(f"unexpected root Vercel outputDirectory: {root_config.get('outputDirectory')!r}")

    root_rewrites = _rewrite_pairs(root_config)
    nested_rewrites = _rewrite_pairs(nested_config)
    expected_rewrites = [
        ("/", "/funding-cards.html"),
        ("/funding-cards", "/funding-cards.html"),
    ]
    if root_rewrites != expected_rewrites:
        _fail(f"root Vercel rewrites drifted: {root_rewrites!r}")
    if nested_rewrites != expected_rewrites:
        _fail(f"nested Vercel rewrites drifted: {nested_rewrites!r}")
    for _source, destination in expected_rewrites:
        target = PUBLIC / destination.lstrip("/")
        if not target.is_file():
            _fail(f"Vercel rewrite destination missing: {destination}")

    if root_config.get("headers") != nested_config.get("headers"):
        _fail("root and nested Vercel response-header policies have diverged")

    html = HTML_PATH.read_text(encoding="utf-8")
    parser = RefParser()
    parser.feed(html)
    local_refs: list[str] = []
    external_refs: list[str] = []
    route_sources = {source for source, _ in expected_rewrites}
    for _tag, _key, raw in parser.refs:
        if raw.startswith("#") or raw.startswith("mailto:"):
            continue
        parts = urlsplit(raw)
        if parts.scheme in {"http", "https"}:
            external_refs.append(raw)
            continue
        path = parts.path
        if not path:
            continue
        if path.startswith("/"):
            local_refs.append(path)
            if path in route_sources:
                continue
            target = PUBLIC / path.lstrip("/")
        else:
            local_refs.append(path)
            target = HTML_PATH.parent / path
        if not target.is_file():
            _fail(f"funding page references missing local asset/path: {raw}")

    canonical_repo = "https://github.com/mohamud1961/Aether"
    if canonical_repo not in external_refs:
        _fail("funding page no longer links to the canonical public repository")

    proof_markers = _require_markers(
        html,
        (
            "9 MONTHS",
            "3 months · £30,000",
            "configure-git-webserver",
            "reported reward",
            "not yet a matched causal A/B",
            "exact public Terra per-task receipt is still pending",
            "CODE + EVIDENCE",
        ),
        label="funding page",
    )

    brief = BRIEF_PATH.read_text(encoding="utf-8")
    proof_markers += _require_markers(
        brief,
        (
            "nine months",
            "£30,000",
            "not yet a causal head-to-head result",
            "exact public Terra per-task receipt",
            "701 passed, 1 skipped",
            "https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml",
            "https://github.com/mohamud1961/Aether/blob/master/evidence/MANIFEST.json",
            "https://github.com/mohamud1961/Aether/tree/master/evidence/qualification",
        ),
        label="research brief",
    )

    print(
        "FUNDING_SITE_VALID "
        f"required_files={len(required_files)} local_refs={len(set(local_refs))} "
        f"external_refs={len(set(external_refs))} routes={len(expected_rewrites)} "
        f"proof_markers={proof_markers}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
