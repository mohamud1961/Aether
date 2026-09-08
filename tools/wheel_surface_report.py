#!/usr/bin/env python3
"""Validate and summarize the built Aether wheel used for public diligence."""
from __future__ import annotations

import argparse
import configparser
from email.parser import Parser
from hashlib import sha256
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "aether.package.wheel_surface.v1"
REQUIRED_RUNTIME_FILES = (
    "aether/launch.py",
    "aether/harbor_agent.py",
    "aether/harbor_runtime_lock.json",
    "aether/launch_schema.json",
    "aether/harbor_subreaper_linux_x86_64",
    "aether/mcp_environment_client.py",
    "aether/rfb_computer_client.py",
)
FORBIDDEN_PREFIXES = (
    "tests/",
    "evidence/",
    "research/",
    "tracking/",
    "website/",
    "docs/",
)


class WheelSurfaceError(RuntimeError):
    pass


def _fail(message: str) -> None:
    raise WheelSurfaceError(message)


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _find_one(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        _fail(f"expected exactly one {suffix!r} entry, found {len(matches)}")
    return matches[0]


def build_report(wheel_path: Path) -> dict[str, object]:
    wheel_path = wheel_path.resolve()
    if not wheel_path.is_file() or wheel_path.suffix != ".whl":
        _fail(f"not a wheel file: {wheel_path}")

    wheel_bytes = wheel_path.read_bytes()
    with zipfile.ZipFile(wheel_path) as archive:
        names = sorted(archive.namelist())
        name_set = set(names)

        missing = [name for name in REQUIRED_RUNTIME_FILES if name not in name_set]
        if missing:
            _fail(f"wheel missing required runtime files: {missing}")

        leaked = [name for name in names if name.startswith(FORBIDDEN_PREFIXES)]
        if leaked:
            _fail(f"wheel contains non-runtime public surfaces: {leaked[:20]}")

        metadata_name = _find_one(names, ".dist-info/METADATA")
        entry_points_name = _find_one(names, ".dist-info/entry_points.txt")
        record_name = _find_one(names, ".dist-info/RECORD")

        metadata = Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
        if metadata.get("Name") != "aether-runtime":
            _fail(f"unexpected package name: {metadata.get('Name')!r}")
        if metadata.get("Version") != "0.3.0":
            _fail(f"unexpected package version: {metadata.get('Version')!r}")
        if metadata.get("Requires-Python") != ">=3.11":
            _fail(f"unexpected Requires-Python: {metadata.get('Requires-Python')!r}")

        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(archive.read(entry_points_name).decode("utf-8"))
        if not parser.has_section("console_scripts"):
            _fail("wheel has no [console_scripts] entry-point section")
        entrypoint = parser.get("console_scripts", "aether", fallback="").strip()
        if entrypoint != "aether.launch:main":
            _fail(f"unexpected aether console entrypoint: {entrypoint!r}")

        record_text = archive.read(record_name).decode("utf-8")
        for required in REQUIRED_RUNTIME_FILES:
            if not any(line.startswith(required + ",") for line in record_text.splitlines()):
                _fail(f"wheel RECORD does not list required runtime file: {required}")

        source_python = sorted(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "aether").rglob("*.py")
        )
        wheel_python = sorted(
            name for name in names if name.startswith("aether/") and name.endswith(".py")
        )
        if wheel_python != source_python:
            missing_python = sorted(set(source_python) - set(wheel_python))
            extra_python = sorted(set(wheel_python) - set(source_python))
            _fail(
                "wheel/source Python surface mismatch: "
                f"missing={missing_python[:20]} extra={extra_python[:20]}"
            )

        required_hashes: dict[str, str] = {}
        for required in REQUIRED_RUNTIME_FILES:
            source = ROOT / required
            if not source.is_file():
                _fail(f"required source file missing: {required}")
            wheel_data = archive.read(required)
            source_data = source.read_bytes()
            if wheel_data != source_data:
                _fail(f"wheel bytes differ from tracked source: {required}")
            required_hashes[required] = _sha(wheel_data)

        return {
            "schema_version": SCHEMA_VERSION,
            "wheel_filename": wheel_path.name,
            "wheel_bytes": len(wheel_bytes),
            "wheel_sha256": _sha(wheel_bytes),
            "package_name": metadata.get("Name"),
            "package_version": metadata.get("Version"),
            "requires_python": metadata.get("Requires-Python"),
            "console_entrypoint": f"aether = {entrypoint}",
            "archive_file_count": len(names),
            "runtime_python_module_count": len(wheel_python),
            "required_runtime_files": list(REQUIRED_RUNTIME_FILES),
            "required_runtime_file_sha256": required_hashes,
            "forbidden_public_surface_entries": leaked,
            "metadata_path": metadata_name,
            "entry_points_path": entry_points_name,
            "record_path": record_name,
            "interpretation": (
                "This proves the built wheel matches the tracked Python runtime surface and "
                "contains the required launch/Harbor/task-bridge package files. It is a CI "
                "qualification artifact, not a separately tagged GitHub release."
            ),
        }


def _summary(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "Aether built-wheel receipt",
            f"schema={report['schema_version']}",
            f"wheel={report['wheel_filename']}",
            f"wheel_bytes={report['wheel_bytes']}",
            f"wheel_sha256={report['wheel_sha256']}",
            f"package={report['package_name']}=={report['package_version']}",
            f"requires_python={report['requires_python']}",
            f"console_entrypoint={report['console_entrypoint']}",
            f"archive_files={report['archive_file_count']}",
            f"runtime_python_modules={report['runtime_python_module_count']}",
            "required_runtime_files=PASS",
            "forbidden_public_surfaces=0",
            "",
            str(report["interpretation"]),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--text", dest="text_path", type=Path)
    args = parser.parse_args()

    report = build_report(args.wheel)
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    text = _summary(report)
    if args.json_path:
        args.json_path.write_text(json_text, encoding="utf-8")
    else:
        print(json_text, end="")
    if args.text_path:
        args.text_path.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
