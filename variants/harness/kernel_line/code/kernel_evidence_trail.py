"""Generic evidence-trail record extraction and projection helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EVIDENCE_TRAIL_VERSION = "kernel_evidence_trail.v1"

_EVIDENCE_ID_RE = re.compile(r"(?i)\bevidence[_\s-]?id(?:s)?\b[^A-Za-z0-9]*([A-Za-z0-9._/-]+)")
_QUOTED_EVIDENCE_IDS_RE = re.compile(r"(?i)\bevidence_ids\b[^[]*\[([^\]]+)\]")
_CLAIM_REQUIREMENT_MARKERS = (
    "evidence id",
    "evidence ids",
    "evidence_id",
    "evidence trail",
    "evidence trace",
    "supporting evidence",
    "supported by evidence",
    "proof",
    "citation",
    "cite",
)
_NEGATIVE_MARKERS = (
    "reject",
    "rejected",
    "stale",
    "missing",
    "mismatch",
    "mismatched",
    "invalid",
    "unsupported",
    "fail",
    "failed",
    "denied",
    "disputed",
    "discard",
)
_POSITIVE_MARKERS = (
    "accept",
    "accepted",
    "selected",
    "supported",
    "verified",
    "pass",
    "passed",
    "keep",
    "derived",
    "transformed",
    "dispatched",
    "frozen",
)
_READ_MARKERS = (
    " cat ",
    " jq ",
    " head ",
    " tail ",
    " sed ",
    " grep ",
    " less ",
    " more ",
    "read_text",
    "read_bytes",
    "json.load",
)
_VERIFY_MARKERS = (
    " sha256sum ",
    " md5sum ",
    " cksum ",
    " stat ",
    " wc ",
    " diff ",
    " cmp ",
    " verify",
    " validate",
    " checksum",
)
_TRANSFORM_MARKERS = (
    " tee ",
    " cp ",
    " mv ",
    ">",
    "write_text",
    "write_bytes",
    "json.dump",
    "json.dumps",
    "open(",
)


@dataclass(frozen=True)
class EvidenceTrailRecord:
    """Compact record of a visible evidence-use event."""

    record_id: str
    receipt_id: str
    action: str
    source_path: str
    evidence_id: str
    claim_supported: bool
    reason: str
    artifact_path: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "receipt_id": self.receipt_id,
            "action": self.action,
            "source_path": self.source_path,
            "evidence_id": self.evidence_id,
            "claim_supported": self.claim_supported,
            "reason": self.reason,
            "artifact_path": self.artifact_path,
            "metadata": dict(self.metadata),
        }


def build_evidence_trail_record(
    *,
    record_id: str,
    receipt_id: str,
    action: str,
    source_path: str,
    evidence_id: str,
    claim_supported: bool,
    reason: str,
    artifact_path: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a normalized evidence-trail record mapping."""

    return EvidenceTrailRecord(
        record_id=str(record_id or ""),
        receipt_id=str(receipt_id or ""),
        action=str(action or "derived"),
        source_path=str(source_path or ""),
        evidence_id=str(evidence_id or ""),
        claim_supported=bool(claim_supported),
        reason=str(reason or ""),
        artifact_path=str(artifact_path or ""),
        metadata=dict(metadata or {}),
    ).to_dict()


def extract_evidence_trail_records_from_receipt(
    receipt: dict[str, Any],
    *,
    workspace_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Extract a single generic evidence-trail record from a receipt."""

    if not isinstance(receipt, dict):
        return []
    receipt_id = str(receipt.get("receipt_id") or "")
    command = str(receipt.get("command") or "")
    stdout_excerpt = str(receipt.get("stdout_excerpt") or "")
    stderr_excerpt = str(receipt.get("stderr_excerpt") or "")
    reason_code = str(receipt.get("reason_code") or "")
    action_type = str(receipt.get("action_type") or "")
    tool_name = str(receipt.get("tool_name") or "")
    changed_files = _string_list(receipt.get("changed_files"))
    deleted_files = _string_list(receipt.get("deleted_files"))
    path_hints = _path_hints(command)
    artifact_inspection = receipt.get("artifact_inspection") if isinstance(receipt.get("artifact_inspection"), dict) else {}
    artifact_refs = _artifact_ref_paths(artifact_inspection)

    evidence_id = _extract_evidence_id(
        [
            receipt_id,
            command,
            stdout_excerpt,
            stderr_excerpt,
            reason_code,
            _json_text(receipt.get("tool_contract_status")),
            _json_text(artifact_inspection),
        ]
    )

    source_path = _pick_path(
        [
            *path_hints,
            *(artifact_refs or []),
            *changed_files,
            *deleted_files,
        ]
    )
    artifact_path = _pick_path(
        [
            *changed_files,
            *(artifact_refs or []),
            source_path,
        ]
    )
    if not source_path and artifact_path:
        source_path = artifact_path

    action, reason = _infer_action(
        receipt=receipt,
        command=command,
        stdout_excerpt=stdout_excerpt,
        stderr_excerpt=stderr_excerpt,
        reason_code=reason_code,
        changed_files=changed_files,
        deleted_files=deleted_files,
        artifact_inspection=artifact_inspection,
    )
    claim_supported = _infer_claim_supported(
        action=action,
        texts=[command, stdout_excerpt, stderr_excerpt, reason_code, _json_text(artifact_inspection)],
    )

    metadata = {
        "tool_name": tool_name,
        "action_type": action_type,
        "reason_code": reason_code,
        "command_sha256": _hash_text(command),
        "stdout_sha256": str(receipt.get("stdout_sha256") or ""),
        "stderr_sha256": str(receipt.get("stderr_sha256") or ""),
        "path_hints": _truncate_list(path_hints, 4),
        "changed_files": _truncate_list(changed_files, 4),
        "deleted_files": _truncate_list(deleted_files, 4),
        "artifact_inspection_kind": str((artifact_inspection.get("command_classification") or {}).get("kind") or ""),
        "artifact_ref_count": len(artifact_refs),
        "tool_contract_status": _compact_mapping(receipt.get("tool_contract_status")),
        "receipt_hash": _hash_text(_json_text(receipt)),
    }

    if workspace_root is not None:
        root = Path(workspace_root)
        source_hash = _hash_file_if_present(root, source_path)
        artifact_hash = _hash_file_if_present(root, artifact_path)
        if source_hash:
            metadata["source_sha256"] = source_hash
        if artifact_hash:
            metadata["artifact_sha256"] = artifact_hash
        if artifact_path:
            metadata["artifact_size_bytes"] = _file_size_if_present(root, artifact_path)

    record_id_seed = "|".join(
        [
            receipt_id,
            action,
            evidence_id,
            source_path,
            artifact_path,
            "supported" if claim_supported else "unsupported",
        ]
    )
    record_id = f"{receipt_id or 'receipt'}:{action}:{_hash_text(record_id_seed)[:10]}"

    return [
        build_evidence_trail_record(
            record_id=record_id,
            receipt_id=receipt_id,
            action=action,
            source_path=source_path,
            evidence_id=evidence_id,
            claim_supported=claim_supported,
            reason=reason,
            artifact_path=artifact_path,
            metadata=metadata,
        )
    ]


def summarize_evidence_trail(records: list[dict[str, Any]], *, max_recent: int = 6) -> dict[str, Any]:
    """Return a compact projection of the trail records."""

    normalized = [_normalize_record(record) for record in records if isinstance(record, dict)]
    action_counts: dict[str, int] = {}
    evidence_ids: list[str] = []
    source_paths: list[str] = []
    artifact_paths: list[str] = []
    receipt_ids: list[str] = []
    supported_record_ids: list[str] = []
    unsupported_record_ids: list[str] = []
    for record in normalized:
        action = str(record.get("action") or "derived")
        action_counts[action] = action_counts.get(action, 0) + 1
        if record.get("claim_supported"):
            supported_record_ids.append(str(record.get("record_id") or ""))
        else:
            unsupported_record_ids.append(str(record.get("record_id") or ""))
        _append_unique(evidence_ids, str(record.get("evidence_id") or ""))
        _append_unique(source_paths, str(record.get("source_path") or ""))
        _append_unique(artifact_paths, str(record.get("artifact_path") or ""))
        _append_unique(receipt_ids, str(record.get("receipt_id") or ""))
    compact_records = [_compact_record(record) for record in normalized]
    recent_records = compact_records[-max(0, int(max_recent)) :] if max_recent > 0 else []
    digest_payload = json.dumps(compact_records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "evidence_trail_version": EVIDENCE_TRAIL_VERSION,
        "record_count": len(normalized),
        "supported_record_count": len(supported_record_ids),
        "unsupported_record_count": len(unsupported_record_ids),
        "action_counts": dict(sorted(action_counts.items())),
        "evidence_ids": evidence_ids,
        "source_paths": source_paths,
        "artifact_paths": artifact_paths,
        "receipt_ids": receipt_ids,
        "supported_record_ids": supported_record_ids,
        "unsupported_record_ids": unsupported_record_ids,
        "recent_records": recent_records,
        "trail_digest": _hash_text(digest_payload) if compact_records else "",
    }


def evaluate_evidence_trail_requirements(
    success_contract: dict[str, Any] | None,
    trail_state_or_records: dict[str, Any] | list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Evaluate whether visible evidence trail requirements are satisfied."""

    contract = dict(success_contract or {})
    contract_status = str(contract.get("status") or "not_declared")
    declared_refs = _dedupe_strings(_string_list(contract.get("visible_evidence_refs")))
    explicit_claim_requirements = _extract_claim_requirements(contract)

    if contract_status not in {"frozen", "revised"}:
        return {
            "status": "not_required",
            "reason_codes": [],
            "required_evidence_ids": declared_refs,
            "missing_evidence_ids": [],
            "explicit_claim_requirements": explicit_claim_requirements,
            "missing_claim_requirements": [],
            "supported_record_ids": [],
            "supported_record_count": 0,
            "declared_contract_status": contract_status,
        }

    if isinstance(trail_state_or_records, dict) and "evidence_trail_version" in trail_state_or_records:
        trail_state = dict(trail_state_or_records)
    else:
        trail_state = summarize_evidence_trail(list(trail_state_or_records or []))

    available_ids = set(_string_list(trail_state.get("evidence_ids")))
    available_paths = set(_string_list(trail_state.get("source_paths"))) | set(_string_list(trail_state.get("artifact_paths")))
    missing_evidence_ids = [
        evidence_id
        for evidence_id in declared_refs
        if evidence_id not in available_ids and evidence_id not in available_paths
    ]
    supported_record_count = int(trail_state.get("supported_record_count") or 0)
    missing_claim_requirements = list(explicit_claim_requirements) if explicit_claim_requirements and supported_record_count <= 0 else []

    if missing_evidence_ids or missing_claim_requirements:
        reason_codes = ["evidence_trail_missing"]
        if missing_evidence_ids:
            reason_codes.append("missing_required_evidence_id")
        if missing_claim_requirements:
            reason_codes.append("semantic_claim_requires_evidence_trail")
        return {
            "status": "fail",
            "reason_codes": _dedupe_strings(reason_codes),
            "required_evidence_ids": declared_refs,
            "missing_evidence_ids": missing_evidence_ids,
            "explicit_claim_requirements": explicit_claim_requirements,
            "missing_claim_requirements": missing_claim_requirements,
            "supported_record_ids": list(_string_list(trail_state.get("supported_record_ids"))),
            "supported_record_count": supported_record_count,
            "declared_contract_status": contract_status,
        }

    if declared_refs or explicit_claim_requirements:
        return {
            "status": "pass",
            "reason_codes": [],
            "required_evidence_ids": declared_refs,
            "missing_evidence_ids": [],
            "explicit_claim_requirements": explicit_claim_requirements,
            "missing_claim_requirements": [],
            "supported_record_ids": list(_string_list(trail_state.get("supported_record_ids"))),
            "supported_record_count": supported_record_count,
            "declared_contract_status": contract_status,
        }

    return {
        "status": "not_required",
        "reason_codes": [],
        "required_evidence_ids": declared_refs,
        "missing_evidence_ids": [],
        "explicit_claim_requirements": explicit_claim_requirements,
        "missing_claim_requirements": [],
        "supported_record_ids": list(_string_list(trail_state.get("supported_record_ids"))),
        "supported_record_count": supported_record_count,
        "declared_contract_status": contract_status,
    }


def project_evidence_trail_state(
    records: list[dict[str, Any]],
    *,
    success_contract: dict[str, Any] | None = None,
    max_recent: int = 6,
) -> dict[str, Any]:
    """Return the compact state projection used by the model and the gates."""

    summary = summarize_evidence_trail(records, max_recent=max_recent)
    requirements = evaluate_evidence_trail_requirements(success_contract, summary)
    return {
        **summary,
        "requirements": requirements,
        "visible_evidence_refs": _dedupe_strings(_string_list((success_contract or {}).get("visible_evidence_refs"))),
    }


def _infer_action(
    *,
    receipt: dict[str, Any],
    command: str,
    stdout_excerpt: str,
    stderr_excerpt: str,
    reason_code: str,
    changed_files: list[str],
    deleted_files: list[str],
    artifact_inspection: dict[str, Any],
) -> tuple[str, str]:
    texts = [command, stdout_excerpt, stderr_excerpt, reason_code, _json_text(artifact_inspection)]
    tool_name = str(receipt.get("tool_name") or "")
    action_type = str(receipt.get("action_type") or "")
    tool_contract = receipt.get("tool_contract_status") if isinstance(receipt.get("tool_contract_status"), dict) else {}

    if _has_any_marker(texts, _NEGATIVE_MARKERS) or str(tool_contract.get("status") or "") == "fail":
        return "rejected", "negative_evidence_markers"

    if _has_any_marker(texts, _POSITIVE_MARKERS) and _extract_evidence_id(texts):
        return "accepted", "explicit_acceptance_marker"

    classification_kind = str((artifact_inspection.get("command_classification") or {}).get("kind") or "")
    if tool_name and tool_name != "raw_bash" and action_type == "native_tool_call":
        return "dispatched", "native_tool_dispatch"
    if classification_kind == "artifact_verify" or _has_any_marker(texts, _VERIFY_MARKERS):
        return "verified", "verification_markers"
    if classification_kind == "artifact_transform" or changed_files or _has_any_marker(texts, _TRANSFORM_MARKERS):
        return "transformed", "artifact_transform_markers"
    if classification_kind == "artifact_read" or _has_any_marker(texts, _READ_MARKERS):
        return "inspected", "readback_markers"
    if deleted_files:
        return "derived", "deleted_artifact_signal"
    if artifact_inspection:
        return "derived", "artifact_inspection_payload"
    if tool_name and action_type:
        return "derived", "generic_tool_action"
    return "inspected", "generic_evidence_signal"


def _infer_claim_supported(*, action: str, texts: list[str]) -> bool:
    joined = " ".join(texts).lower()
    if action == "rejected":
        return False
    if any(marker in joined for marker in _NEGATIVE_MARKERS):
        return False
    return action in {"accepted", "derived", "dispatched", "inspected", "transformed", "verified"}


def _extract_claim_requirements(contract: dict[str, Any]) -> list[str]:
    requirements: list[str] = []
    for section_name in ("criteria", "required_checks", "done_checklist"):
        for item in _string_list(contract.get(section_name)):
            lowered = item.lower()
            if any(marker in lowered for marker in _CLAIM_REQUIREMENT_MARKERS):
                requirements.append(item)
    return _dedupe_strings(requirements)


def _extract_evidence_id(texts: list[str]) -> str:
    candidates: list[str] = []
    for text in texts:
        if not isinstance(text, str) or not text:
            continue
        match = _EVIDENCE_ID_RE.search(text)
        if match:
            candidates.append(match.group(1))
        match_list = _QUOTED_EVIDENCE_IDS_RE.search(text)
        if match_list:
            for token in re.findall(r"""['"]([^'"]+)['"]""", match_list.group(1)):
                candidates.append(token)
    return _first_non_empty(candidates)


def _artifact_ref_paths(artifact_inspection: dict[str, Any]) -> list[str]:
    refs = artifact_inspection.get("artifact_refs")
    if not isinstance(refs, list):
        return []
    out: list[str] = []
    for ref in refs:
        if isinstance(ref, dict):
            path = ref.get("path")
            if isinstance(path, str) and path:
                out.append(path)
        elif isinstance(ref, str) and ref:
            out.append(ref)
    return _dedupe_strings(out)


def _pick_path(paths: list[str]) -> str:
    for path in paths:
        if isinstance(path, str) and path:
            return path
    return ""


def _has_any_marker(texts: list[str], markers: tuple[str, ...]) -> bool:
    joined = " ".join(texts).lower()
    return any(marker.strip().lower() in joined for marker in markers)


def _path_hints(command: str) -> list[str]:
    if not command:
        return []
    try:
        import shlex

        tokens = shlex.split(command, posix=True)
    except Exception:
        tokens = command.split()
    hints: list[str] = []
    for token in tokens:
        candidate = token.strip("'\" ,;:()[]{}")
        if not candidate or candidate.startswith("-"):
            continue
        if candidate.startswith(("/", "./", "../", "~/")) or "/" in candidate or Path(candidate).suffix.lower() in {
            ".csv",
            ".json",
            ".jsonl",
            ".log",
            ".md",
            ".py",
            ".sh",
            ".txt",
            ".toml",
            ".xml",
            ".yaml",
            ".yml",
        }:
            hints.append(candidate)
    return _dedupe_strings(hints)


def _hash_file_if_present(root: Path, rel_path: str) -> str:
    if not rel_path:
        return ""
    candidate = Path(rel_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        if not candidate.exists() or not candidate.is_file():
            return ""
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


def _file_size_if_present(root: Path, rel_path: str) -> int:
    if not rel_path:
        return 0
    candidate = Path(rel_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return int(candidate.stat().st_size) if candidate.exists() and candidate.is_file() else 0
    except Exception:
        return 0


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(record.get("record_id") or ""),
        "receipt_id": str(record.get("receipt_id") or ""),
        "action": str(record.get("action") or "derived"),
        "source_path": str(record.get("source_path") or ""),
        "evidence_id": str(record.get("evidence_id") or ""),
        "claim_supported": bool(record.get("claim_supported")),
        "reason": str(record.get("reason") or ""),
        "artifact_path": str(record.get("artifact_path") or ""),
        "metadata": _compact_mapping(record.get("metadata")),
    }


def _compact_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_record(record)
    return {
        "record_id": normalized["record_id"],
        "receipt_id": normalized["receipt_id"],
        "action": normalized["action"],
        "source_path": normalized["source_path"],
        "evidence_id": normalized["evidence_id"],
        "claim_supported": normalized["claim_supported"],
        "reason": normalized["reason"],
        "artifact_path": normalized["artifact_path"],
        "metadata": _compact_mapping(normalized["metadata"]),
    }


def _compact_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for key, observed in value.items():
        if isinstance(observed, (str, int, float, bool)) and not isinstance(observed, bool):
            compact[key] = observed
        elif isinstance(observed, bool):
            compact[key] = observed
        elif isinstance(observed, list):
            compact[key] = _truncate_list([str(item) for item in observed if isinstance(item, (str, int, float, bool))], 4)
        elif isinstance(observed, dict):
            compact[key] = _compact_mapping(observed)
    return compact


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _dedupe_strings(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen or not value:
            continue
        seen.add(value)
        out.append(value)
    return out


def _append_unique(values: list[str], candidate: str) -> None:
    if not candidate or candidate in values:
        return
    values.append(candidate)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except Exception:
        return str(value)


def _truncate_list(values: list[str], max_len: int) -> list[str]:
    if len(values) <= max_len:
        return values
    return values[:max_len] + [f"... ({len(values) - max_len} more omitted)"]


def _first_non_empty(values: list[str]) -> str:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return ""
