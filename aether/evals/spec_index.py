from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Mapping

from .utils.hashes import canonical_json_dumps


ID_PATTERN = re.compile(
    r"\b(?:CT|IM|PL|TG|CX|LC|OA|SD|CL|US)-\d{2,}\b"
    r"|\bCAP-DISC-\d{2,}\b"
    r"|\b[A-H]\d+\b"
    r"|\bCS-[A-Za-z][A-Za-z0-9]*\b"
    r"|\bUS-[A-Za-z][A-Za-z0-9]*\b"
)


def extract_ids_from_markdown(markdown_path: Path) -> List[str]:
    text = markdown_path.read_text(encoding="utf-8")
    ids = sorted(set(ID_PATTERN.findall(text)))
    return ids


def build_spec_index(spec_dir: str | Path) -> Dict[str, Mapping[str, object]]:
    root = Path(spec_dir)
    if not root.exists():
        raise FileNotFoundError(f"Spec directory not found: {root}")

    index: Dict[str, Mapping[str, object]] = {}
    for md_path in sorted(root.glob("*.md"), key=lambda path: path.name):
        ids = extract_ids_from_markdown(md_path)
        line_count = len(md_path.read_text(encoding="utf-8").splitlines())
        index[md_path.name] = {
            "ids": ids,
            "id_count": len(ids),
            "line_count": line_count,
        }

    return index


def write_spec_index(spec_dir: str | Path, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "v1_1_spec_id_index",
        "spec_dir": Path(spec_dir).as_posix(),
        "packs": build_spec_index(spec_dir),
    }
    out.write_text(canonical_json_dumps(payload) + "\n", encoding="utf-8")
    return out


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build markdown test-id index for V1.1 specs")
    parser.add_argument("--spec-dir", required=True, help="Directory containing V1.1 markdown packs")
    parser.add_argument("--out", required=True, help="Path to write generated JSON index")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    write_spec_index(args.spec_dir, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
