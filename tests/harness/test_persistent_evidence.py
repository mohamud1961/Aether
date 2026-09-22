from __future__ import annotations

import pytest

from aether.ledger import Receipt
from aether.persistent_evidence import (
    is_persistent_completion_evidence,
    is_persistent_primary_action_result,
)


def test_job_disposition_is_indexed_as_action_result_but_not_completion_evidence() -> None:
    receipt = Receipt(
        receipt_id="step-1:action:disposition",
        step=1,
        kind="job_disposition",
        success=True,
        summary="job disposition verify: optional",
        payload={"job_id": "job-1", "relevance": "optional"},
    )

    assert is_persistent_primary_action_result(receipt) is True
    assert is_persistent_completion_evidence(receipt) is False


@pytest.mark.parametrize(
    ("kind", "success"),
    [
        ("completion_record_revision", True),
        ("completion_record_update", False),
    ],
)
def test_completion_record_result_is_indexed_but_never_completion_evidence(
    kind: str,
    success: bool,
) -> None:
    receipt = Receipt(
        receipt_id=f"step-2:action:{kind}",
        step=2,
        kind=kind,
        success=success,
        summary="completion-record bookkeeping result",
        payload={"semantic_authority": "frontier"},
    )

    assert is_persistent_primary_action_result(receipt) is True
    assert is_persistent_completion_evidence(receipt) is False
