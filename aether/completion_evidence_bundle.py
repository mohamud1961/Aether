from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .artifact_store import ArtifactStore


@dataclass(frozen=True)
class CompletionEvidenceBundle:
    bundle_id: str
    run_id: str
    receipt_refs: List[str]
    manifest_refs: List[str]
    verifier_result_refs: List[str]
    approval_refs: List[str]
    workspace_fingerprint_at_verify: str
    plan_id: str
    plan_version_id: int
    completion_contract_ref: str
    intent_contract_ref: str
    log_root_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "completion_evidence_bundle.v1.1",
            "bundle_id": self.bundle_id,
            "run_id": self.run_id,
            "receipt_refs": sorted(set(self.receipt_refs)),
            "manifest_refs": sorted(set(self.manifest_refs)),
            "verifier_result_refs": sorted(set(self.verifier_result_refs)),
            "approval_refs": sorted(set(self.approval_refs)),
            "workspace_fingerprint_at_verify": self.workspace_fingerprint_at_verify,
            "plan_id": self.plan_id,
            "plan_version_id": int(self.plan_version_id),
            "completion_contract_ref": self.completion_contract_ref,
            "intent_contract_ref": self.intent_contract_ref,
            "log_root_hash": self.log_root_hash,
        }


# Backward-compatible export name used by existing tests.
CompletionEvidenceBundleV1 = CompletionEvidenceBundle


@dataclass(frozen=True)
class CompletionEvidenceBundleReceipt:
    artifact_ref: str
    bundle_hash: str
    payload: Dict[str, Any]


def write_completion_evidence_bundle(
    artifact_store: ArtifactStore,
    bundle: CompletionEvidenceBundle,
) -> CompletionEvidenceBundleReceipt:
    payload = bundle.to_dict()
    _validate_required(payload)
    artifact, payload_hash = artifact_store.write_json_canonical(payload)
    return CompletionEvidenceBundleReceipt(
        artifact_ref=artifact.artifact_id,
        bundle_hash=payload_hash,
        payload=payload,
    )


def validate_completion_evidence_bundle_stage_c(
    *,
    artifact_store: ArtifactStore,
    bundle_receipt: CompletionEvidenceBundleReceipt,
    current_workspace_fingerprint: str,
) -> None:
    payload = bundle_receipt.payload
    _validate_required(payload)

    for key in ("receipt_refs", "manifest_refs", "verifier_result_refs", "approval_refs"):
        refs = payload.get(key)
        if not isinstance(refs, list):
            raise ValueError(f"completion bundle field must be list: {key}")
        for ref in refs:
            if not isinstance(ref, str) or not ref:
                raise ValueError(f"completion bundle invalid ref in {key}")
            artifact_store.read_bytes(ref)

    for single_ref_field in ("completion_contract_ref", "intent_contract_ref"):
        ref = payload.get(single_ref_field)
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"completion bundle missing field: {single_ref_field}")
        artifact_store.read_bytes(ref)

    workspace_at_verify = payload.get("workspace_fingerprint_at_verify")
    if workspace_at_verify != current_workspace_fingerprint:
        raise ValueError("completion bundle workspace fingerprint mismatch")


def _validate_required(payload: Dict[str, Any]) -> None:
    required_str_fields = (
        "bundle_id",
        "run_id",
        "workspace_fingerprint_at_verify",
        "plan_id",
        "completion_contract_ref",
        "intent_contract_ref",
        "log_root_hash",
    )
    for key in required_str_fields:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"completion bundle missing required field: {key}")

    plan_version_id = payload.get("plan_version_id")
    if not isinstance(plan_version_id, int) or plan_version_id < 1:
        raise ValueError("completion bundle plan_version_id must be positive int")

    for key in ("receipt_refs", "manifest_refs", "verifier_result_refs"):
        value = payload.get(key)
        if not isinstance(value, list) or not value:
            raise ValueError(f"completion bundle requires at least one {key}")
    approval_refs = payload.get("approval_refs")
    if not isinstance(approval_refs, list):
        raise ValueError("completion bundle approval_refs must be a list")
