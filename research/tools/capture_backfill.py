#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "research/intake/normalized/manifests/corpus__deduped.json"
DEFAULT_RECORDS = ROOT / "research/intake/records"
DEFAULT_REPORT = ROOT / "research/intake/normalized/capture/2026-03-31__capture_backfill_report.json"
DEFAULT_BLOCKED = ROOT / "research/intake/rejected/2026-03-31__capture_backfill__blocked.json"
USER_AGENT = "Mozilla/5.0 harnesseng-capture-backfill"
TARGET_DIRS = {
    "paper": "papers",
    "documentation": "docs",
    "benchmark": "benchmarks",
    "code": "codebases",
    "trace": "traces",
    "issue": "issues",
    "postmortem": "postmortems",
}
PLACEHOLDER_HOSTS = {"example.com", "example.org", "engineering.example.org", "traces.example.org"}


class CaptureBlocked(Exception):
    def __init__(self, reason: str, attempted_fetches: list[dict], next_action: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.attempted_fetches = attempted_fetches
        self.next_action = next_action


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.skip_tags = {"head", "script", "style", "nav", "header", "footer", "svg"}
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.skip_tags:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.skip_tags and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sink_dir(record: dict) -> Path:
    kind = record["artifact_class"]
    return ROOT / "research/sources" / TARGET_DIRS[kind] / record["source_id"]


def capture_path_for(record: dict) -> Path:
    return sink_dir(record) / "capture.json"


def placeholder_domain(url: str) -> bool:
    host = urllib.parse.urlsplit(url).netloc.lower()
    return host in PLACEHOLDER_HOSTS or host.startswith("www.example.")


def fetch_url(url: str, attempted_fetches: list[dict], kind: str, timeout: int) -> tuple[str, bytes, dict]:
    attempt = {"kind": kind, "url": url}
    attempted_fetches.append(attempt)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            final_url = resp.geturl()
            headers = dict(resp.headers.items())
            attempt.update(
                {
                    "status": getattr(resp, "status", 200),
                    "final_url": final_url,
                    "content_type": headers.get("Content-Type"),
                }
            )
            return final_url, body, headers
    except urllib.error.HTTPError as exc:
        attempt.update({"status": exc.code, "error": str(exc)})
        raise
    except Exception as exc:
        attempt.update({"error": str(exc)})
        raise


def safe_text(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def file_capture_metadata(
    record: dict,
    kind: str,
    fetch_method: str,
    artifact_files: list[str],
    notes: list[str],
    capture_quality: str,
) -> dict:
    out_dir = sink_dir(record)
    return {
        "source_id": record["source_id"],
        "canonical_url": record["canonical_url"],
        "captured_at": now_utc(),
        "fetch_method": fetch_method,
        "artifact_files": artifact_files,
        "content_hashes": {name: sha256_file(out_dir / name) for name in artifact_files},
        "kind": kind,
        "title": record["title"],
        "provided_date": record.get("date"),
        "capture_quality": capture_quality,
        "notes": notes,
    }


def validate_capture(record: dict) -> tuple[bool, str, dict | None]:
    cap_path = capture_path_for(record)
    if not cap_path.exists():
        return False, "capture.json missing", None
    try:
        capture = load_json(cap_path)
    except Exception as exc:
        return False, f"capture.json unreadable: {exc}", None
    if capture.get("canonical_url") != record["canonical_url"]:
        return False, "capture.json canonical_url mismatch", capture
    artifact_files = capture.get("artifact_files")
    if not isinstance(artifact_files, list) or not artifact_files:
        return False, "capture.json artifact_files missing", capture
    hashes = capture.get("content_hashes")
    if not isinstance(hashes, dict):
        return False, "capture.json content_hashes missing", capture
    for rel_name in artifact_files:
        if not (sink_dir(record) / rel_name).exists():
            return False, f"artifact file missing: {rel_name}", capture
        if not hashes.get(rel_name):
            return False, f"content hash missing: {rel_name}", capture
    return True, "valid", capture


def update_record_linkage(record_path: Path, record: dict, capture: dict) -> bool:
    changed = False
    artifact_relpath = str(sink_dir(record).relative_to(ROOT))
    if record.get("artifact_relpath") != artifact_relpath:
        record["artifact_relpath"] = artifact_relpath
        changed = True
    desired = {
        "capture_exists": True,
        "capture_path": str(capture_path_for(record).relative_to(ROOT)),
        "capture_kind": capture.get("kind"),
        "capture_canonical_url": capture.get("canonical_url"),
        "canonical_url_match": capture.get("canonical_url") == record["canonical_url"],
    }
    current = record.get("capture_metadata_matches")
    if current != desired:
        record["capture_metadata_matches"] = desired
        changed = True
    if changed:
        write_json(record_path, record)
    return changed


def write_html_capture(record: dict, attempted_fetches: list[dict], timeout: int, kind: str, notes: list[str]) -> dict:
    if placeholder_domain(record["canonical_url"]):
        raise CaptureBlocked(
            "placeholder canonical URL; local capture would not back a real accepted source",
            [{"kind": "skip", "url": record["canonical_url"], "result": "placeholder_domain"}],
            "Replace the accepted record with a real source before capture backfill.",
        )
    final_url, body, _ = fetch_url(record["canonical_url"], attempted_fetches, "canonical_html", timeout)
    out_dir = sink_dir(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact.html").write_bytes(body)
    (out_dir / "artifact.txt").write_text(html_to_text(safe_text(body)) + "\n")
    if final_url != record["canonical_url"]:
        notes.append(f"Canonical URL redirected to {final_url} during capture.")
    capture = file_capture_metadata(
        record,
        kind,
        "urllib_html_capture",
        ["artifact.html", "artifact.txt"],
        notes,
        "full_html_plus_text",
    )
    write_json(out_dir / "capture.json", capture)
    return capture


def infer_paper_pdf_url(record: dict, html: str | None) -> str | None:
    url = record["canonical_url"]
    parsed = urllib.parse.urlsplit(url)
    if "arxiv.org" in parsed.netloc:
        match = re.search(r"(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(?:v\d+)?", parsed.path)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    if parsed.netloc == "doi.org" and "arxiv." in parsed.path:
        match = re.search(r"arxiv\.([0-9]{4}\.[0-9]{4,5})", parsed.path)
        if match:
            return f"https://arxiv.org/pdf/{match.group(1)}.pdf"
    if parsed.netloc == "openreview.net":
        paper_id = urllib.parse.parse_qs(parsed.query).get("id", [None])[0]
        if paper_id:
            return f"https://openreview.net/pdf?id={paper_id}"
    if parsed.netloc == "aclanthology.org" and not parsed.path.endswith(".pdf"):
        return url.rstrip("/") + ".pdf"
    if parsed.path.endswith(".pdf"):
        return url
    if html:
        for match in re.finditer(r'href="([^"]+?\.pdf[^"]*)"', html, flags=re.IGNORECASE):
            pdf_url = urllib.parse.urljoin(url, match.group(1).replace("&amp;", "&"))
            if urllib.parse.urlsplit(pdf_url).netloc == parsed.netloc:
                return pdf_url
    return None


def write_paper_capture(record: dict, attempted_fetches: list[dict], timeout: int) -> dict:
    if placeholder_domain(record["canonical_url"]):
        raise CaptureBlocked(
            "placeholder canonical URL; paper capture would not back a real source",
            [{"kind": "skip", "url": record["canonical_url"], "result": "placeholder_domain"}],
            "Replace the accepted record with a real paper URL before capture backfill.",
        )
    notes: list[str] = []
    out_dir = sink_dir(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_body = None
    html_final_url = None
    direct_pdf_url = infer_paper_pdf_url(record, None)
    pdf_url = direct_pdf_url
    if not pdf_url:
        html_final_url, html_body, _ = fetch_url(record["canonical_url"], attempted_fetches, "canonical_html", timeout)
        pdf_url = infer_paper_pdf_url(record, safe_text(html_body))
    if pdf_url:
        try:
            pdf_final_url, pdf_body, headers = fetch_url(pdf_url, attempted_fetches, "paper_pdf", timeout)
            is_pdf = pdf_body.startswith(b"%PDF") or "pdf" in (headers.get("Content-Type", "").lower())
            if is_pdf:
                (out_dir / "artifact.pdf").write_bytes(pdf_body)
                if pdf_final_url != pdf_url:
                    notes.append(f"PDF URL redirected to {pdf_final_url} during capture.")
                if html_final_url and html_final_url != record["canonical_url"]:
                    notes.append(f"Canonical URL redirected to {html_final_url} during PDF resolution.")
                capture = file_capture_metadata(
                    record,
                    "paper",
                    "urllib_same_source_pdf",
                    ["artifact.pdf"],
                    notes,
                    "full_pdf",
                )
                write_json(out_dir / "capture.json", capture)
                return capture
            notes.append(f"Derived PDF endpoint did not return PDF bytes: {pdf_url}")
        except Exception as exc:
            notes.append(f"PDF fetch failed, used HTML fallback instead: {exc}")
    if html_body is None:
        html_final_url, html_body, _ = fetch_url(record["canonical_url"], attempted_fetches, "canonical_html", timeout)
    (out_dir / "artifact.html").write_bytes(html_body)
    (out_dir / "artifact.txt").write_text(html_to_text(safe_text(html_body)) + "\n")
    notes.append("Saved HTML/TXT fallback because no stable PDF endpoint was available.")
    if html_final_url and html_final_url != record["canonical_url"]:
        notes.append(f"Canonical URL redirected to {html_final_url} during capture.")
    capture = file_capture_metadata(
        record,
        "paper",
        "urllib_html_fallback",
        ["artifact.html", "artifact.txt"],
        notes,
        "fallback_html_plus_text",
    )
    write_json(out_dir / "capture.json", capture)
    return capture


def github_repo_parts(url: str) -> tuple[str, str] | None:
    parts = [piece for piece in urllib.parse.urlsplit(url).path.split("/") if piece]
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def github_ref_from_url(url: str) -> str | None:
    parts = [piece for piece in urllib.parse.urlsplit(url).path.split("/") if piece]
    if len(parts) >= 4 and parts[2] in {"blob", "tree"}:
        return parts[3]
    return None


def looks_like_reproducible_github_ref(ref: str | None) -> bool:
    if not ref:
        return False
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return True
    if ref in {"main", "master", "dev", "develop", "trunk"}:
        return False
    return bool(re.fullmatch(r"v?\d+(?:\.\d+)+(?:[-._A-Za-z0-9]+)?", ref))


def github_commit_from_html(html: str) -> str | None:
    patterns = [
        r'"/[^"]+/commit/([0-9a-f]{40})"',
        r'"commitOid":"([0-9a-f]{40})"',
        r'data-turbo-click="[^"]*?/commit/([0-9a-f]{40})"',
    ]
    counts = Counter()
    for pattern in patterns:
        for sha in re.findall(pattern, html):
            counts[sha] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def write_code_capture(record: dict, attempted_fetches: list[dict], timeout: int) -> dict:
    url = record["canonical_url"]
    parsed = urllib.parse.urlsplit(url)
    if placeholder_domain(url) or "/example/" in parsed.path:
        raise CaptureBlocked(
            "placeholder canonical URL; reproducible code archive would be fake",
            [{"kind": "skip", "url": url, "result": "placeholder_domain"}],
            "Replace the accepted record with a real repository URL before capture backfill.",
        )
    if parsed.netloc != "github.com":
        raise CaptureBlocked(
            "no supported same-source reproducible archive strategy for non-GitHub code source",
            [{"kind": "skip", "url": url, "result": "unsupported_host"}],
            "Capture this source manually with a reproducible archive and then add capture.json.",
        )
    repo = github_repo_parts(url)
    if not repo:
        raise CaptureBlocked(
            "could not parse GitHub repository coordinates from canonical URL",
            [{"kind": "skip", "url": url, "result": "unparseable_url"}],
            "Repair the accepted record canonical URL.",
        )
    owner, repo_name = repo
    final_url, html_body, _ = fetch_url(url, attempted_fetches, "canonical_html", timeout)
    ref = github_ref_from_url(final_url)
    archive_body = None
    notes: list[str] = []
    resolved_commit = None
    if looks_like_reproducible_github_ref(ref):
        try:
            archive_url = (
                f"https://github.com/{owner}/{repo_name}/archive/{ref}.zip"
                if re.fullmatch(r"[0-9a-f]{40}", ref or "")
                else f"https://github.com/{owner}/{repo_name}/archive/refs/tags/{ref}.zip"
            )
            _, archive_body, _ = fetch_url(archive_url, attempted_fetches, "repo_archive_zip", timeout)
            notes.append(f"Captured reproducible GitHub archive from ref {ref}.")
            resolved_commit = ref
        except Exception:
            archive_body = None
    if archive_body is None:
        commit_sha = github_commit_from_html(safe_text(html_body))
        if not commit_sha:
            raise CaptureBlocked(
                "could not resolve an immutable GitHub commit SHA from the canonical page",
                attempted_fetches,
                "Capture this repo manually at an immutable commit or update the source to a pinned GitHub URL.",
            )
        archive_url = f"https://github.com/{owner}/{repo_name}/archive/{commit_sha}.zip"
        _, archive_body, _ = fetch_url(archive_url, attempted_fetches, "repo_archive_zip", timeout)
        resolved_commit = commit_sha
        notes.append(f"Resolved immutable GitHub commit SHA {commit_sha} from {final_url}.")
    out_dir = sink_dir(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "artifact.zip").write_bytes(archive_body)
    capture = file_capture_metadata(
        record,
        "code",
        "urllib_github_archive_zip",
        ["artifact.zip"],
        notes,
        "full_repo_archive",
    )
    capture["resolved_commit"] = resolved_commit
    write_json(out_dir / "capture.json", capture)
    return capture


def capture_record(record: dict, attempted_fetches: list[dict], timeout: int) -> dict:
    kind = record["artifact_class"]
    if kind in {"documentation", "benchmark", "issue", "postmortem"}:
        capture_kind = {"documentation": "doc", "benchmark": "benchmark", "issue": "issue", "postmortem": "postmortem"}[kind]
        return write_html_capture(record, attempted_fetches, timeout, capture_kind, [])
    if kind == "paper":
        return write_paper_capture(record, attempted_fetches, timeout)
    if kind == "code":
        return write_code_capture(record, attempted_fetches, timeout)
    raise CaptureBlocked(
        "trace capture requires a reproducible raw export and no supported raw export endpoint was identified from the canonical URL",
        [{"kind": "skip", "url": record["canonical_url"], "result": "unsupported_trace"}],
        "Capture the raw trace export manually, or update the source to a direct export URL.",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT))
    parser.add_argument("--blocked-path", default=str(DEFAULT_BLOCKED))
    parser.add_argument("--source-id", action="append", dest="source_ids")
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()

    accepted_source_ids = load_json(Path(args.manifest))["accepted_source_ids"]
    if args.source_ids:
        accepted_source_ids = [sid for sid in accepted_source_ids if sid in set(args.source_ids)]
    blocked_items: list[dict] = []
    touched_records: list[str] = []
    touched_capture_dirs: list[str] = []
    status_by_source: dict[str, str] = {}
    replaced_invalid_capture_source_ids: list[str] = []
    preexisting_valid = 0
    newly_captured = 0

    for source_id in accepted_source_ids:
        record_path = DEFAULT_RECORDS / f"{source_id}.json"
        record = load_json(record_path)
        valid, reason, capture = validate_capture(record)
        if valid and capture:
            preexisting_valid += 1
            status_by_source[source_id] = "captured_preexisting"
            if update_record_linkage(record_path, record, capture):
                touched_records.append(str(record_path.relative_to(ROOT)))
            continue

        attempted_fetches: list[dict] = []
        if capture_path_for(record).exists():
            replaced_invalid_capture_source_ids.append(source_id)
        try:
            capture = capture_record(record, attempted_fetches, args.timeout)
            status_by_source[source_id] = "captured_new"
            newly_captured += 1
            touched_capture_dirs.append(str(sink_dir(record).relative_to(ROOT)))
            record = load_json(record_path)
            if update_record_linkage(record_path, record, capture):
                touched_records.append(str(record_path.relative_to(ROOT)))
        except CaptureBlocked as blocked:
            status_by_source[source_id] = "blocked"
            blocked_items.append(
                {
                    "source_id": source_id,
                    "canonical_url": record["canonical_url"],
                    "artifact_target_dir": str(sink_dir(record).relative_to(ROOT)),
                    "block_reason": blocked.reason if reason == "capture.json missing" else f"{reason}; {blocked.reason}",
                    "attempted_fetches": blocked.attempted_fetches,
                    "next_action": blocked.next_action,
                }
            )
        except Exception as exc:
            status_by_source[source_id] = "blocked"
            blocked_items.append(
                {
                    "source_id": source_id,
                    "canonical_url": record["canonical_url"],
                    "artifact_target_dir": str(sink_dir(record).relative_to(ROOT)),
                    "block_reason": f"{reason}; unexpected fetch failure: {exc}",
                    "attempted_fetches": attempted_fetches,
                    "next_action": "Retry with network access or inspect the source manually.",
                }
            )

    report = {
        "run_date": "2026-03-31",
        "accepted_source_count": len(accepted_source_ids),
        "preexisting_valid_capture_count": preexisting_valid,
        "newly_captured_count": newly_captured,
        "still_missing_count": len(accepted_source_ids) - preexisting_valid - newly_captured - len(blocked_items),
        "blocked_count": len(blocked_items),
        "touched_records": sorted(set(touched_records)),
        "touched_capture_dirs": sorted(set(touched_capture_dirs)),
        "blocked_source_ids": sorted(item["source_id"] for item in blocked_items),
        "replaced_invalid_capture_source_ids": sorted(set(replaced_invalid_capture_source_ids)),
        "source_statuses": status_by_source,
    }
    write_json(Path(args.report_path), report)
    write_json(Path(args.blocked_path), blocked_items)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
