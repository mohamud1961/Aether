#!/usr/bin/env python3
"""Bulk extract repo-local paper PDFs into a canonical text surface."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT / "research" / "sources" / "papers"
DEFAULT_OUTPUT_DIR = ROOT / "research" / "sources" / "papers" / "papers_text"
EXTRACTION_METHOD = "pypdf"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract paper PDFs into research/sources/papers/papers_text."
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing paper PDFs. Default: research/sources/papers",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to receive extracted text and metadata.",
    )
    parser.add_argument(
        "--paper-key",
        action="append",
        default=[],
        help="Only extract the specified paper key. Repeatable.",
    )
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def paper_key_for(pdf_path: Path) -> str:
    if pdf_path.name == "artifact.pdf" and pdf_path.parent.name.startswith("src_pap_"):
        return pdf_path.parent.name
    return re.sub(r"[^A-Za-z0-9._-]+", "_", pdf_path.stem)


def capture_path_for(pdf_path: Path) -> Path | None:
    capture_path = pdf_path.parent / "capture.json"
    return capture_path if capture_path.exists() else None


def load_capture(capture_path: Path | None) -> dict:
    if capture_path is None:
        return {}
    return json.loads(capture_path.read_text(encoding="utf-8"))


def normalize_page(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"[\ud800-\udfff]", "\ufffd", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def infer_title(capture_title: str | None, page_texts: list[str]) -> tuple[str | None, str | None]:
    if capture_title:
        return capture_title, "capture"
    for page_text in page_texts:
        for line in page_text.splitlines():
            candidate = re.sub(r"\s+", " ", line).strip()
            if re.fullmatch(r"\d+", candidate):
                continue
            candidate = re.split(r"\babstract\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip(" -:")
            if candidate:
                return candidate[:240], "extracted_first_line"
    return None, None


def render_text_output(page_texts: list[str]) -> str:
    chunks = []
    for page_number, page_text in enumerate(page_texts, start=1):
        if page_text:
            chunks.append(f"--- PAGE {page_number} ---\n{page_text}")
    if not chunks:
        return "No extractable text was produced for this PDF. See the matching .meta.json file.\n"
    return "\n\n".join(chunks) + "\n"


def classify_quality(
    *,
    page_count: int,
    total_chars: int,
    characters_per_page: float,
    nonempty_pages: int,
    parser_warning_count: int,
    page_error_count: int,
    replacement_character_count: int,
    open_error: str | None,
) -> tuple[str, list[str]]:
    if open_error:
        return "failed", [open_error]
    if page_count == 0 or nonempty_pages == 0 or total_chars == 0:
        return "ocr_needed", ["no extractable text"]

    ocr_reasons: list[str] = []
    min_expected_chars = max(500, 120 * page_count)
    if total_chars < min_expected_chars:
        ocr_reasons.append(
            f"low extracted text volume ({total_chars} chars across {page_count} pages)"
        )
    if nonempty_pages / page_count < 0.5:
        ocr_reasons.append(
            f"only {nonempty_pages} of {page_count} pages produced extractable text"
        )
    if ocr_reasons:
        return "ocr_needed", ocr_reasons

    caveat_reasons: list[str] = []
    if parser_warning_count:
        caveat_reasons.append(
            f"{parser_warning_count} parser warnings during extraction"
        )
    if page_error_count:
        caveat_reasons.append(f"{page_error_count} page extraction errors")
    if replacement_character_count:
        caveat_reasons.append(
            f"{replacement_character_count} replacement characters in extracted text"
        )
    if characters_per_page < 500:
        caveat_reasons.append(
            f"low extracted text density ({characters_per_page:.2f} chars/page)"
        )
    if caveat_reasons:
        return "usable_with_caveats", caveat_reasons
    return "clean", ["text extracted without parser or page-level errors"]


def synthesis_policy_for(quality_flag: str) -> tuple[bool, str]:
    if quality_flag == "clean":
        return True, "full_formal_source_use"
    if quality_flag == "usable_with_caveats":
        return True, "formal_source_use_with_caveats"
    return False, "not_substantively_read"


def extract_pdf(pdf_path: Path) -> dict:
    stderr_buffer = io.StringIO()
    page_errors: list[dict[str, str | int]] = []
    page_texts: list[str] = []
    open_error: str | None = None
    page_count = 0
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            reader = PdfReader(str(pdf_path))
            page_count = len(reader.pages)
            for page_number, page in enumerate(reader.pages, start=1):
                try:
                    raw_text = page.extract_text() or ""
                    page_texts.append(normalize_page(raw_text))
                except Exception as exc:  # pragma: no cover - defensive guard
                    page_errors.append({"page": page_number, "error": str(exc)})
                    page_texts.append("")
    except Exception as exc:
        open_error = str(exc)

    parser_warnings = [line.strip() for line in stderr_buffer.getvalue().splitlines() if line.strip()]
    text_output = render_text_output(page_texts)
    total_chars = sum(len(page_text) for page_text in page_texts if page_text)
    characters_per_page = round(total_chars / page_count, 2) if page_count else 0.0
    nonempty_pages = sum(1 for page_text in page_texts if page_text)
    replacement_character_count = sum(page_text.count("\ufffd") for page_text in page_texts)
    title, title_source = infer_title(None, page_texts)
    quality_flag, quality_reasons = classify_quality(
        page_count=page_count,
        total_chars=total_chars,
        characters_per_page=characters_per_page,
        nonempty_pages=nonempty_pages,
        parser_warning_count=len(parser_warnings),
        page_error_count=len(page_errors),
        replacement_character_count=replacement_character_count,
        open_error=open_error,
    )
    return {
        "page_count": page_count,
        "nonempty_pages": nonempty_pages,
        "characters_extracted": total_chars,
        "characters_per_page": characters_per_page,
        "parser_warnings": parser_warnings,
        "page_errors": page_errors,
        "replacement_character_count": replacement_character_count,
        "quality_flag": quality_flag,
        "quality_reasons": quality_reasons,
        "title_guess": title,
        "title_guess_source": title_source,
        "text_output": text_output,
        "open_error": open_error,
    }


def iter_papers(source_dir: Path, allowed_keys: set[str]) -> list[tuple[str, Path, Path | None]]:
    jobs: list[tuple[str, Path, Path | None]] = []
    seen_keys: dict[str, str] = {}
    for pdf_path in sorted(source_dir.rglob("*.pdf")):
        paper_key = paper_key_for(pdf_path)
        if allowed_keys and paper_key not in allowed_keys:
            continue
        existing = seen_keys.get(paper_key)
        if existing:
            raise SystemExit(f"Duplicate paper key {paper_key!r}: {existing} and {pdf_path}")
        seen_keys[paper_key] = str(pdf_path)
        jobs.append((paper_key, pdf_path, capture_path_for(pdf_path)))
    return jobs


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_review_summary(output_dir: Path, records: list[dict], generated_at: str) -> None:
    quality_counts = Counter(record["quality_flag"] for record in records)
    readable_count = sum(1 for record in records if record["readable_for_deep_synthesis"])
    unread_records = [
        record for record in records if not record["readable_for_deep_synthesis"]
    ]
    caveated_records = [
        record for record in records if record["quality_flag"] == "usable_with_caveats"
    ]
    lines = [
        "# Paper Extraction Review Summary",
        "",
        f"- generated_at_utc: {generated_at}",
        f"- total_papers: {len(records)}",
        f"- clean: {quality_counts.get('clean', 0)}",
        f"- usable_with_caveats: {quality_counts.get('usable_with_caveats', 0)}",
        f"- ocr_needed: {quality_counts.get('ocr_needed', 0)}",
        f"- failed: {quality_counts.get('failed', 0)}",
        f"- readable_for_deep_synthesis: {readable_count}",
        f"- unread_for_deep_synthesis: {len(unread_records)}",
        "",
        "## Readability Rule",
        "",
        "- `clean`: counts as read and supports full formal-source use.",
        "- `usable_with_caveats`: counts as read, but downstream claims must weaken confidence where damaged sections matter.",
        "- `ocr_needed`: does not count as substantively read yet.",
        "- `failed`: does not count as substantively read yet.",
        "",
        "## Caveated Papers",
        "",
    ]
    if caveated_records:
        for record in caveated_records:
            reason_text = "; ".join(record["quality_reasons"])
            title = record.get("title") or "Untitled extraction"
            lines.append(
                f"- `{record['paper_key']}`: {title}; allowed_use={record['allowed_use']}; reasons={reason_text}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Rescue Queue", ""])
    if unread_records:
        for record in unread_records:
            reason_text = "; ".join(record["quality_reasons"])
            title = record.get("title") or "Untitled extraction"
            lines.append(
                f"- `{record['paper_key']}`: {title}; quality_flag={record['quality_flag']}; reasons={reason_text}"
            )
    else:
        lines.append("- None on this pass.")
    lines.extend(["", "## High-Priority Unread Papers", "", "- None on this pass."])
    (output_dir / "review_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    jobs = iter_papers(source_dir, set(args.paper_key))
    generated_at = now_utc()
    quality_counts: Counter[str] = Counter()
    records: list[dict] = []

    for paper_key, pdf_path, capture_path in jobs:
        capture = load_capture(capture_path)
        extraction = extract_pdf(pdf_path)
        quality_counts[extraction["quality_flag"]] += 1
        text_path = output_dir / f"{paper_key}.txt"
        meta_path = output_dir / f"{paper_key}.meta.json"
        text_path.write_text(extraction.pop("text_output"), encoding="utf-8")
        readable_for_deep_synthesis, allowed_use = synthesis_policy_for(
            extraction["quality_flag"]
        )
        title = capture.get("title") or extraction.get("title_guess")
        metadata = {
            "paper_key": paper_key,
            "title": title,
            "title_source": "capture" if capture.get("title") else extraction.get("title_guess_source"),
            "source_id": capture.get("source_id"),
            "canonical_url": capture.get("canonical_url"),
            "source_path": repo_rel(pdf_path),
            "capture_path": repo_rel(capture_path) if capture_path else None,
            "output_text_path": repo_rel(text_path),
            "output_meta_path": repo_rel(meta_path),
            "generated_at_utc": generated_at,
            "extraction_method": EXTRACTION_METHOD,
            "readable_for_deep_synthesis": readable_for_deep_synthesis,
            "allowed_use": allowed_use,
            **extraction,
        }
        write_json(meta_path, metadata)
        records.append(metadata)

    caveated_papers = [
        {
            "paper_key": record["paper_key"],
            "quality_flag": record["quality_flag"],
            "source_path": record["source_path"],
            "title": record.get("title"),
        }
        for record in records
        if record["quality_flag"] == "usable_with_caveats"
    ]
    rescue_queue = [
        {
            "paper_key": record["paper_key"],
            "quality_flag": record["quality_flag"],
            "source_path": record["source_path"],
            "title": record.get("title"),
        }
        for record in records
        if record["quality_flag"] in {"ocr_needed", "failed"}
    ]

    manifest = {
        "generated_at_utc": generated_at,
        "source_dir": repo_rel(source_dir),
        "output_dir": repo_rel(output_dir),
        "extraction_method": EXTRACTION_METHOD,
        "paper_count": len(jobs),
        "quality_counts": dict(sorted(quality_counts.items())),
        "deep_synthesis_readability_counts": {
            "readable": sum(
                1 for record in records if record["readable_for_deep_synthesis"]
            ),
            "unread": sum(
                1 for record in records if not record["readable_for_deep_synthesis"]
            ),
        },
        "caveated_papers": caveated_papers,
        "rescue_queue": rescue_queue,
        "review_summary_path": repo_rel(output_dir / "review_summary.md"),
    }
    write_json(output_dir / "manifest.json", manifest)
    write_review_summary(output_dir, records, generated_at)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
