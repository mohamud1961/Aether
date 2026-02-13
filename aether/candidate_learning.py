from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .artifact_store import ArtifactStore
from .event_log import EventLog
from .policy_config import PolicyConfig


@dataclass(frozen=True)
class CandidateLearning:
    learning_id: str
    source_type: str
    source_receipt_ids: List[str]
    content: str
    content_hash: str
    provenance_tag: str
    created_at: str


@dataclass(frozen=True)
class CandidateLearningReceipt:
    artifact_ref: str
    payload_hash: str
    payload: Dict[str, Any]


def create_candidate_learning(
    *,
    source_type: str,
    source_receipt_ids: List[str],
    content: str,
    run_id: str,
    step_id: int,
    created_at: Optional[str] = None,
) -> CandidateLearning:
    normalized_source = _normalize_source_type(source_type)
    created = created_at or _utc_now_iso()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    provenance_tag = f"{run_id}:{step_id}"
    learning_id = hashlib.sha256(
        f"{content_hash}:{provenance_tag}".encode("utf-8")
    ).hexdigest()
    deduped_receipts = sorted({item for item in source_receipt_ids if isinstance(item, str) and item})

    return CandidateLearning(
        learning_id=learning_id,
        source_type=normalized_source,
        source_receipt_ids=deduped_receipts,
        content=content,
        content_hash=content_hash,
        provenance_tag=provenance_tag,
        created_at=created,
    )


def write_candidate_learning(
    *,
    learning: CandidateLearning,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> CandidateLearningReceipt:
    payload = asdict(learning)
    artifact_ref, payload_hash = artifact_store.write_json_canonical(payload)
    event_log.append_event(
        {
            "event_type": "CANDIDATE_LEARNING_WRITTEN",
            "timestamp": timestamp,
            "cwd": cwd,
            "learning_id": learning.learning_id,
            "source_type": learning.source_type,
            "content_hash": learning.content_hash,
            "artifact_refs": [artifact_ref.artifact_id],
            "source_receipt_ids": learning.source_receipt_ids,
            "provenance_tag": learning.provenance_tag,
        }
    )
    return CandidateLearningReceipt(
        artifact_ref=artifact_ref.artifact_id,
        payload_hash=payload_hash,
        payload=payload,
    )


def maybe_capture_candidate_learning(
    *,
    policy: PolicyConfig,
    source_type: str,
    source_receipt_ids: List[str],
    content: str,
    run_id: str,
    step_id: int,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> Optional[CandidateLearningReceipt]:
    if not _write_allowed(source_type=source_type, source_receipt_ids=source_receipt_ids):
        return None

    learning = create_candidate_learning(
        source_type=source_type,
        source_receipt_ids=source_receipt_ids,
        content=content,
        run_id=run_id,
        step_id=step_id,
        created_at=timestamp,
    )
    receipt = write_candidate_learning(
        learning=learning,
        artifact_store=artifact_store,
        event_log=event_log,
        timestamp=timestamp,
        cwd=cwd,
    )

    # Steering remains opt-in by policy. Captures are always non-steering by default.
    if not policy.candidate_learning_enabled:
        return receipt
    return receipt


def _normalize_source_type(value: str) -> str:
    candidate = str(value).strip().lower()
    if candidate not in {"verified_outcome", "user_correction"}:
        raise ValueError(f"unsupported candidate learning source_type: {value}")
    return candidate


def _write_allowed(*, source_type: str, source_receipt_ids: List[str]) -> bool:
    normalized = _normalize_source_type(source_type)
    if normalized == "verified_outcome":
        return bool(source_receipt_ids)
    if normalized == "user_correction":
        return True
    return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
