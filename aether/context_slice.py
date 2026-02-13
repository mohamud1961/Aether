from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Dict, Optional

from .artifact_store import ArtifactStore
from .event_log import EventLog
from .redaction import redact


@dataclass(frozen=True)
class ContextSliceV1:
    step_id: int
    timestamp: str
    context_pack_hash: str
    manifest_hash: str
    context_pack_ref: str
    manifest_ref: str
    model_request_hash: str
    model_request_ref: str
    workspace_fingerprint_hash: str
    policy_profile_id: str
    plan_version_id: Optional[str] = None
    completion_contract_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "version": "context_slice.v1",
            "step_id": self.step_id,
            "timestamp": self.timestamp,
            "context_pack_hash": self.context_pack_hash,
            "manifest_hash": self.manifest_hash,
            "context_pack_ref": self.context_pack_ref,
            "manifest_ref": self.manifest_ref,
            "model_request_hash": self.model_request_hash,
            "model_request_ref": self.model_request_ref,
            "workspace_fingerprint_hash": self.workspace_fingerprint_hash,
            "policy_profile_id": self.policy_profile_id,
            "plan_version_id": self.plan_version_id,
            "completion_contract_id": self.completion_contract_id,
        }
        return payload


@dataclass(frozen=True)
class ContextSliceReceipt:
    artifact_ref: str
    slice_hash: str
    payload: Dict[str, Any]


def write_context_slice(
    artifact_store: ArtifactStore,
    context_slice: ContextSliceV1,
    *,
    event_log: Optional[EventLog] = None,
    timestamp: Optional[str] = None,
    cwd: Optional[str] = None,
) -> ContextSliceReceipt:
    payload = context_slice.to_dict()
    _validate_required(payload)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    redacted_json, redactions = redact(payload_json)
    if redactions:
        payload = json.loads(redacted_json)
        if event_log is not None and isinstance(timestamp, str) and isinstance(cwd, str):
            event_log.append_event(
                {
                    "event_type": "REDACTION_APPLIED",
                    "timestamp": timestamp,
                    "cwd": cwd,
                    "count": sum(record.count for record in redactions),
                    "types": sorted({record.redaction_type for record in redactions}),
                    "object_type": "context_slice",
                }
            )
    artifact, payload_hash = artifact_store.write_json_canonical(payload)
    return ContextSliceReceipt(
        artifact_ref=artifact.artifact_id,
        slice_hash=payload_hash,
        payload=payload,
    )


def _validate_required(payload: Dict[str, Any]) -> None:
    required = (
        "context_pack_hash",
        "manifest_hash",
        "context_pack_ref",
        "manifest_ref",
        "model_request_hash",
        "model_request_ref",
        "workspace_fingerprint_hash",
        "policy_profile_id",
    )
    for key in required:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"context slice missing required field: {key}")
