import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


USER_AGENT = "Mozilla/5.0 harnesseng-source-harvester"
ROOT = Path(__file__).resolve().parents[2]


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    clean = parts._replace(fragment="")
    return urllib.parse.urlunsplit(clean).rstrip("/")


def make_source_id(kind: str, locator: str) -> str:
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:12]
    return f"src_{kind}_{digest}"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def extract_arxiv_id(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})(?:v[0-9]+)?", url)
    return match.group(1) if match else None


def resolve_arxiv_id(entry: dict) -> str:
    arxiv_id = entry.get("arxiv_id") or extract_arxiv_id(entry.get("url"))
    if arxiv_id:
        return arxiv_id
    title = entry["title"]
    query = urllib.parse.quote(f'ti:"{title}"')
    feed_url = f"https://export.arxiv.org/api/query?search_query={query}&start=0&max_results=8"
    feed = ET.fromstring(fetch_bytes(feed_url))
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    target = normalize_title(title)
    best_id = None
    best_score = 0.0
    for node in feed.findall("atom:entry", ns):
        node_title = node.findtext("atom:title", default="", namespaces=ns)
        node_id = node.findtext("atom:id", default="", namespaces=ns)
        match = re.search(r"/abs/([0-9]{4}\.[0-9]{4,5})(?:v[0-9]+)?$", node_id)
        if not match:
            continue
        score = difflib.SequenceMatcher(None, target, normalize_title(node_title)).ratio()
        if score > best_score:
            best_score = score
            best_id = match.group(1)
    if not best_id or best_score < 0.72:
        raise RuntimeError(f"Could not resolve arXiv ID for title: {title}")
    return best_id


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harvest_paper(entry: dict) -> dict:
    arxiv_id = resolve_arxiv_id(entry)
    canonical_url = f"https://arxiv.org/abs/{arxiv_id}"
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    source_id = make_source_id("pap", f"arxiv:{arxiv_id}")
    out_dir = ROOT / "research" / "sources" / "papers" / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "artifact.pdf"
    if not pdf_path.exists():
        pdf_path.write_bytes(fetch_bytes(pdf_url))
    capture = {
        "source_id": source_id,
        "title": entry["title"],
        "kind": "paper",
        "canonical_url": canonical_url,
        "resolved_arxiv_id": arxiv_id,
        "provided_date": entry.get("provided_date"),
        "origins": entry.get("origins", []),
        "usage_tags": entry.get("usage_tags", []),
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fetch_method": "urllib",
        "artifact_files": ["artifact.pdf"],
        "content_hashes": {"artifact.pdf": sha256_file(pdf_path)}
    }
    write_json(out_dir / "capture.json", capture)
    return {
        "source_id": source_id,
        "title": entry["title"],
        "canonical_url": canonical_url,
        "artifact_relpath": str(pdf_path.relative_to(ROOT))
    }


def harvest_doc(entry: dict) -> dict:
    canonical_url = normalize_url(entry["url"])
    source_id = make_source_id("doc", canonical_url)
    out_dir = ROOT / "research" / "sources" / "docs" / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "artifact.html"
    text_path = out_dir / "artifact.txt"
    if not html_path.exists():
        html_path.write_bytes(fetch_bytes(entry["url"]))
    html_bytes = html_path.read_bytes()
    if not text_path.exists():
        text_path.write_text(html_to_text(html_bytes.decode("utf-8", errors="replace")) + "\n")
    capture = {
        "source_id": source_id,
        "title": entry["title"],
        "kind": "doc",
        "doc_type": entry.get("doc_type", "official_doc"),
        "canonical_url": canonical_url,
        "provided_date": entry.get("provided_date"),
        "origins": entry.get("origins", []),
        "usage_tags": entry.get("usage_tags", []),
        "captured_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fetch_method": "urllib",
        "artifact_files": ["artifact.html", "artifact.txt"],
        "content_hashes": {
            "artifact.html": sha256_file(html_path),
            "artifact.txt": sha256_file(text_path)
        }
    }
    write_json(out_dir / "capture.json", capture)
    return {
        "source_id": source_id,
        "title": entry["title"],
        "canonical_url": canonical_url,
        "artifact_relpath": str(out_dir.relative_to(ROOT))
    }


def write_index(path: Path, rows: list[dict], label: str) -> None:
    lines = [f"# {label}", "", "| Source ID | Title | URL | Artifact |", "|---|---|---|---|"]
    for row in sorted(rows, key=lambda item: item["title"].lower()):
        artifact = row["artifact_relpath"]
        lines.append(
            f"| `{row['source_id']}` | {row['title']} | {row['canonical_url']} | `{artifact}` |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.manifest).read_text())
    papers, docs, report = [], [], {"captured": [], "failed": []}

    for entry in payload["entries"]:
        try:
            record = harvest_paper(entry) if entry["kind"] == "paper" else harvest_doc(entry)
            report["captured"].append(record)
            (papers if entry["kind"] == "paper" else docs).append(record)
        except Exception as exc:
            report["failed"].append({"title": entry["title"], "kind": entry["kind"], "error": str(exc)})

    write_index(ROOT / "research" / "sources" / "papers" / "USER_SUPPLIED_INDEX.md", papers, "User-Supplied Papers")
    write_index(ROOT / "research" / "sources" / "docs" / "INDEX.md", docs, "Captured Docs")
    write_json(Path(args.report), report)


if __name__ == "__main__":
    main()
