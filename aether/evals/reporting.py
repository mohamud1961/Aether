from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping
from xml.etree import ElementTree as ET

from .models import TestResult
from .utils.hashes import canonical_json_dumps


def _serialize_result(result: TestResult) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "test_id": result.test_id,
        "name": result.name,
        "pack": result.pack,
        "profile": result.profile,
        "mode": result.mode,
        "passed": result.passed,
        "fail_signature": result.fail_signature,
        "required_events": result.required_events,
        "observed_events": result.observed_events,
        "evidence_refs": result.evidence_refs,
        "timings": result.timings,
    }
    if result.details:
        payload["details"] = result.details
    return payload


def write_report_json(
    out_dir: Path,
    results: Iterable[TestResult],
    metadata: Mapping[str, Any],
) -> Path:
    payload = {
        "schema_version": "eval-report.v1_1",
        "metadata": dict(metadata),
        "tests": [_serialize_result(result) for result in results],
    }
    path = out_dir / "report.json"
    path.write_text(canonical_json_dumps(payload) + "\n", encoding="utf-8")
    return path


def write_report_md(
    out_dir: Path,
    results: Iterable[TestResult],
    metadata: Mapping[str, Any],
) -> Path:
    result_list = list(results)
    passed = sum(1 for result in result_list if result.passed)
    failed = len(result_list) - passed

    lines: List[str] = []
    lines.append("# Eval Report")
    lines.append("")
    lines.append(f"- pack: `{metadata.get('pack')}`")
    lines.append(f"- profile: `{metadata.get('profile')}`")
    lines.append(f"- mode: `{metadata.get('mode')}`")
    lines.append(f"- artifact_dir: `{metadata.get('artifact_dir')}`")
    if metadata.get("fixture_name"):
        lines.append(f"- fixture: `{metadata.get('fixture_name')}`")
    lines.append(f"- total: `{len(result_list)}`")
    lines.append(f"- passed: `{passed}`")
    lines.append(f"- failed: `{failed}`")
    lines.append("")
    lines.append("| Test ID | Pack | Result | Fail Signature |")
    lines.append("|---|---|---|---|")

    for result in result_list:
        status = "PASS" if result.passed else "FAIL"
        fail_signature = result.fail_signature or ""
        lines.append(f"| {result.test_id} | {result.pack} | {status} | {fail_signature} |")

    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_junit_xml(
    out_dir: Path,
    results: Iterable[TestResult],
    metadata: Mapping[str, Any],
) -> Path:
    result_list = list(results)
    suite = ET.Element(
        "testsuite",
        attrib={
            "name": str(metadata.get("pack", "evals")),
            "tests": str(len(result_list)),
            "failures": str(sum(1 for result in result_list if not result.passed)),
            "errors": "0",
        },
    )

    for result in result_list:
        testcase = ET.SubElement(
            suite,
            "testcase",
            attrib={
                "classname": result.pack,
                "name": result.test_id,
            },
        )
        if not result.passed:
            failure = ET.SubElement(
                testcase,
                "failure",
                attrib={"message": result.fail_signature or "unknown"},
            )
            failure.text = json.dumps(_serialize_result(result), sort_keys=True)

    tree = ET.ElementTree(suite)
    path = out_dir / "junit.xml"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return path


def write_reports(
    out_dir: str | Path,
    results: Iterable[TestResult],
    metadata: Mapping[str, Any],
) -> Dict[str, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    result_list = list(results)
    json_path = write_report_json(out_path, result_list, metadata)
    md_path = write_report_md(out_path, result_list, metadata)
    junit_path = write_junit_xml(out_path, result_list, metadata)

    return {
        "report_json": json_path,
        "report_md": md_path,
        "junit_xml": junit_path,
    }
