from __future__ import annotations

import json

import jsonschema
import pytest

from aether.providers.azure_model import (
    AzureProviderOutputError,
    _PCR_VERIFIER_DIRECT_TURN_SCHEMA,
    unwrap_verifier_direct_turn,
)
from aether.verifier import parse_model_verifier_result
from aether.verify_completion_protocol import _provider_protocol_correction
from aether.verify_inspection_requests import _typed_inspections_from_missing_evidence


def _direct(kind: str, locator: str) -> dict[str, object]:
    return {
        "kind": kind,
        "locator": locator,
        "limit": None,
        "offset": None,
        "span": None,
        "clause_ids": None,
        "proof_ids": None,
    }


def _uncertain(*, typed: list[dict[str, object]]) -> dict[str, object]:
    return {
        "turn": {
            "verdict": "uncertain_missing_evidence",
            "confidence": 0.95,
            "summary": "Need one live HTTP observation.",
            "findings": [],
            "missing_evidence_requests": [
                "Observe the live HTTP response body for http://127.0.0.1:8080/hello.html."
            ],
            "missing_inspection_requests": typed,
            "completion_evidence": [],
            "method_validity": None,
        }
    }


def test_pcr_read_file_cannot_consume_http_url() -> None:
    wrapper = {"turn": {"kind": "inspect", "requests": [_direct(
        "read_file", "http://127.0.0.1:8080/hello.html"
    )]}}
    # The compact provider schema alone cannot express a conditional locator
    # pattern, so the transport canonicalizer is the fail-closed boundary.
    jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(AzureProviderOutputError) as exc:
        unwrap_verifier_direct_turn(json.dumps(wrapper))
    assert exc.value.code == "provider_direct_turn_locator_route_mismatch"


def test_pcr_probe_http_requires_full_http_url() -> None:
    wrapper = {"turn": {"kind": "inspect", "requests": [_direct(
        "probe_http", "127.0.0.1:8080/hello.html"
    )]}}
    jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    with pytest.raises(AzureProviderOutputError) as exc:
        unwrap_verifier_direct_turn(json.dumps(wrapper))
    assert exc.value.code == "provider_direct_turn_locator_route_mismatch"


def test_pcr_typed_missing_http_request_canonicalizes_to_runtime_probe() -> None:
    wrapper = _uncertain(typed=[_direct(
        "probe_http", "http://127.0.0.1:8080/hello.html"
    )])
    jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps(wrapper))
    decoded = json.loads(canonical)
    typed = decoded["missing_inspection_requests"]
    assert typed == [{"kind": "probe_http", "target": "http://127.0.0.1:8080/hello.html"}]
    mapping = receipt["provider_pcr_verifier_compact_locator_mapping"]
    assert mapping[0]["provider_kind"] == "probe_http"
    assert mapping[0]["runtime_kind"] == "probe_http"

    result = parse_model_verifier_result(decoded)
    requests = _typed_inspections_from_missing_evidence(result)
    assert len(requests) == 1
    assert requests[0].kind == "probe_http"
    assert requests[0].target == "http://127.0.0.1:8080/hello.html"


def test_pcr_uncertain_verdict_requires_typed_missing_field_even_when_empty() -> None:
    wrapper = _uncertain(typed=[])
    jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    del wrapper["turn"]["missing_inspection_requests"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)


def test_route_mismatch_correction_says_rejected_before_execution() -> None:
    payload = _provider_protocol_correction("provider_direct_turn_locator_route_mismatch")
    assert payload["rejected_response_executed"] == "false"
    assert "probe_http" in payload["instruction"]
    assert "read_file" in payload["instruction"]
    assert "rejected before execution" in payload["instruction"]


def test_non_uncertain_verdict_cannot_smuggle_typed_missing_request() -> None:
    wrapper = {
        "turn": {
            "verdict": "completed",
            "confidence": "high",
            "summary": "done",
            "findings": [],
            "missing_evidence_requests": [],
            "missing_inspection_requests": [_direct(
                "probe_http", "http://127.0.0.1:8080/"
            )],
            "completion_evidence": [],
            "method_validity": None,
        }
    }
    # Keep the strict provider shape compact and stable. The provider transport
    # canonicalizer removes this semantically inapplicable field before the
    # runtime parser, avoiding a wasted correction call.
    jsonschema.validate(wrapper, _PCR_VERIFIER_DIRECT_TURN_SCHEMA)
    canonical, receipt = unwrap_verifier_direct_turn(json.dumps(wrapper))
    decoded = json.loads(canonical)
    assert decoded["missing_inspection_requests"] == []
    assert receipt["provider_pcr_verifier_settled_missing_inspections_canonicalized"] is True
    assert parse_model_verifier_result(decoded).verdict == "completed"

    # Runtime stays fail-closed as defence in depth for non-provider callers.
    payload = dict(wrapper["turn"])
    payload["missing_inspection_requests"] = [{
        "kind": "probe_http", "target": "http://127.0.0.1:8080/"
    }]
    with pytest.raises(ValueError, match="only valid for uncertain_missing_evidence"):
        parse_model_verifier_result(payload)


def test_pcr_direct_span_is_bounded_by_runtime_per_result_budget() -> None:
    for span in (1, 8192):
        request = _direct("read_file", "/app/result.txt")
        request["span"] = span
        jsonschema.validate(
            {"turn": {"kind": "inspect", "requests": [request]}},
            _PCR_VERIFIER_DIRECT_TURN_SCHEMA,
        )

    for span in (0, 8193):
        request = _direct("read_file", "/app/result.txt")
        request["span"] = span
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(
                {"turn": {"kind": "inspect", "requests": [request]}},
                _PCR_VERIFIER_DIRECT_TURN_SCHEMA,
            )
