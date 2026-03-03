from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ._common import events_of, fail_case, make_case, pass_case


PACK = "candidate"


def _candidate_memory_slices(ctx: TestExecutionContext) -> List[Mapping[str, object]]:
    memory: List[Mapping[str, object]] = []
    for compiled in events_of(ctx, "CONTEXTPACK_COMPILED"):
        slices = compiled.get("slice_list")
        if not isinstance(slices, list):
            continue
        for item in slices:
            if not isinstance(item, Mapping):
                continue
            layer = str(item.get("layer", "")).upper()
            source = str(item.get("source_ref", ""))
            if layer == "MEMORY" or source.startswith("candidate:"):
                memory.append(item)
    return memory


def _cl_01_candidate_inert_by_default(ctx: TestExecutionContext):
    run_start = events_of(ctx, "run_START")
    candidate_enabled = any(bool(event.get("candidate_learning_enabled")) for event in run_start)

    memory = _candidate_memory_slices(ctx)
    if memory and not candidate_enabled:
        return fail_case("candidate_learning_steering_enabled_by_default")

    return pass_case()


def _cl_02_candidate_write_requires_verified_source(ctx: TestExecutionContext):
    memory = _candidate_memory_slices(ctx)
    if not memory:
        return pass_case()

    verifier_pass = any(bool(event.get("pass")) for event in events_of(ctx, "VERIFIER_RESULT"))
    explicit_correction = any(
        event.get("approval_reason_code") == "USER_CORRECTION"
        for event in events_of(ctx, "APPROVAL_GRANTED")
    )

    if not verifier_pass and not explicit_correction:
        return fail_case("candidate_learning_unverified_source")

    return pass_case()


def _cl_03_candidate_learning_provenance(ctx: TestExecutionContext):
    memory = _candidate_memory_slices(ctx)
    if not memory:
        return pass_case()

    for item in memory:
        receipt_ids = item.get("source_receipt_ids")
        manifest_ids = item.get("source_manifest_ids")
        if not isinstance(receipt_ids, list) or not receipt_ids:
            return fail_case("candidate_learning_missing_source_receipts")
        if not isinstance(manifest_ids, list) or not manifest_ids:
            return fail_case("candidate_learning_missing_source_manifests")

        for ref in [*receipt_ids, *manifest_ids]:
            if isinstance(ref, str):
                failure = require_hash_exists(ctx.artifact_store, ref)
                if failure is not None:
                    return fail_case(failure.fail_signature, missing_ref=ref)

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="CL-01", name="Candidate Learning Inert by Default", objective="Candidate memory is inert unless explicit policy enables steering.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cl_01_candidate_inert_by_default),
        make_case(pack=PACK, test_id="CL-02", name="Candidate Write Source Gating", objective="Candidate learning writes require verified outcomes or explicit correction.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cl_02_candidate_write_requires_verified_source),
        make_case(pack=PACK, test_id="CL-03", name="Candidate Provenance Tagging", objective="Candidate learning records must include source receipts and manifests.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_cl_03_candidate_learning_provenance),
    ]
