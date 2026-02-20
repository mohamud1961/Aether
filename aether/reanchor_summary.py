from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .artifact_store import ArtifactStore


@dataclass(frozen=True)
class ReanchorSummaryV1:
    step_id: int
    timestamp: str
    trigger_code: str
    reason: str
    cleared_sections: List[str]
    cleared_source_refs: List[str]
    remains_true_refs: List[str]
    evidence_refs: List[str]
    next_action: str
    rebuilt_components: List[str]
    cleared_components: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "reanchor_summary.v1.1",
            "step_id": self.step_id,
            "timestamp": self.timestamp,
            "trigger_code": self.trigger_code,
            "reason": self.reason,
            "cleared_sections": list(self.cleared_sections),
            "cleared_source_refs": list(self.cleared_source_refs),
            "remains_true_refs": list(self.remains_true_refs),
            "evidence_refs": list(self.evidence_refs),
            "next_action": self.next_action,
            "rebuilt_components": list(self.rebuilt_components),
            "cleared_components": list(self.cleared_components),
        }


@dataclass(frozen=True)
class ReanchorSummaryReceipt:
    artifact_ref: str
    summary_hash: str
    payload: Dict[str, Any]


def write_reanchor_summary(
    artifact_store: ArtifactStore,
    summary: ReanchorSummaryV1,
) -> ReanchorSummaryReceipt:
    payload = summary.to_dict()
    artifact, payload_hash = artifact_store.write_json_canonical(payload)
    return ReanchorSummaryReceipt(
        artifact_ref=artifact.artifact_id,
        summary_hash=payload_hash,
        payload=payload,
    )
