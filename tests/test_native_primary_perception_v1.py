from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace

import pytest

from aether.execution import ArtifactInspection
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger, Receipt
from aether.model_hooks import ModelHooks
from aether.pcr_provider_protocol import pcr_primary_turn_schema
from aether.native_primary_perception import (
    MAX_NATIVE_IMAGE_BYTES,
    stage_same_primary_native_image,
)
from aether.providers.azure_model import AzureModelCallable, AzureModelError
from aether.runtime_ir import ActionRequest, EnvMap, FIXED_KERNEL_TOOL_SURFACE


def _turn(path: str = "/app/input.txt") -> str:
    return json.dumps({
        "turn": {
            "kind": "act",
            "action": {
                "kind": "read_file",
                "arguments": {"path": path},
            },
        }
    })


def _function_call(n: int, path: str = "/app/input.txt") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{n}", type="function_call", status="completed",
        call_id=f"call-{n}", name="read_file", arguments=json.dumps({"arguments": {"path": path}}),
    )


def _response(n: int, path: str = "/app/input.txt") -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp-{n}", status="completed", output=[_function_call(n, path)],
        usage=None, reasoning=None, error=None, incomplete_details=None,
    )


class _FakeResponses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.rows:
            raise AssertionError("no fake response remains")
        return self.rows.pop(0)

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _FakeClient:
    def __init__(self, rows: list[object]) -> None:
        self.responses = _FakeResponses(rows)


def _model(rows: list[object]) -> tuple[AzureModelCallable, _FakeClient]:
    client = _FakeClient(rows)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-luna",
        effort="low",
        role="solver",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
    )
    return model, client


def _call(model: AzureModelCallable, content: str, *, commit: bool = True) -> str:
    raw = model.call_with_telemetry_scope(
        [{"role": "user", "content": content}],
        max_output_tokens=16000,
        run_id="run-a",
        task_id="task-a",
    )
    if commit:
        model.commit_pending_response(run_id="run-a", task_id="task-a")
    return raw


def _image_identity(raw: bytes, *, media_type: str = "image/png", path: str = "image.png") -> dict[str, object]:
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "schema_version": "aether.artifact_identity.v1",
        "sha256": digest,
        "bytes": len(raw),
        "media_type": media_type,
        "path": path,
        "source": "test",
        "generation": "g1",
        "handle": f"artifact:sha256:{digest}",
    }


class _BytesExecutor:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def read_file_bytes(self, _path: str) -> bytes:
        return self.raw


def _base_receipt(raw: bytes, *, media_type: str = "image/png", path: str = "image.png") -> Receipt:
    return Receipt(
        receipt_id="step-1:inspect:inspect",
        step=1,
        kind="artifact_inspection",
        success=False,
        summary="metadata only",
        failure_class="perception_required",
        payload={
            "path": path,
            "mode": "image",
            "metadata": {
                "artifact_identity": _image_identity(raw, media_type=media_type, path=path),
                "semantic_content_available": False,
            },
        },
    )


def test_modelhooks_native_stage_is_scope_bound_and_makes_no_model_call() -> None:
    class Solver:
        def __init__(self) -> None:
            self.rows: list[dict[str, object]] = []

        def stage_native_image_observation(self, **kwargs: object) -> bool:
            self.rows.append(dict(kwargs))
            return True

    solver = Solver()
    hooks = ModelHooks(solver, lambda *_a, **_k: "{}", run_id="run-x", task_id="task-x")  # type: ignore[arg-type]
    raw = b"pixels"
    assert hooks.stage_primary_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_path="x.png",
        source_receipt_id="r1",
    ) is True
    assert solver.rows == [{
        "image_bytes": raw,
        "media_type": "image/png",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_path": "x.png",
        "source_receipt_id": "r1",
        "run_id": "run-x",
        "task_id": "task-x",
    }]


def test_native_stage_requires_exact_identity_and_never_persists_raw_bytes_in_receipt() -> None:
    raw = b"\x89PNG\r\nexact-pixels"
    staged: list[dict[str, object]] = []
    hooks = SimpleNamespace(
        stage_primary_native_image_observation=lambda **kwargs: staged.append(dict(kwargs)) or True,
    )
    kernel = SimpleNamespace(active_hooks=hooks)
    receipt = stage_same_primary_native_image(
        kernel,
        SimpleNamespace(action_id="inspect"),
        1,
        _BytesExecutor(raw),
        _base_receipt(raw),
    )
    assert receipt is not None and receipt.success is True
    assert receipt.payload["extraction_route"] == "same_primary_native_image"
    assert receipt.payload["extraction_authority"] == "exact_pixels_no_textual_intermediary"
    assert receipt.payload["native_primary_raw_bytes_persisted_in_receipt"] is False
    serialized = json.dumps(receipt.payload, sort_keys=True, default=str)
    assert base64.b64encode(raw).decode("ascii") not in serialized
    assert staged[0]["image_bytes"] == raw


def test_native_stage_identity_drift_fails_closed_without_provider_staging() -> None:
    original = b"original"
    changed = b"changed"
    called = False

    def stage(**_kwargs: object) -> bool:
        nonlocal called
        called = True
        return True

    receipt = stage_same_primary_native_image(
        SimpleNamespace(active_hooks=SimpleNamespace(stage_primary_native_image_observation=stage)),
        SimpleNamespace(action_id="inspect"),
        1,
        _BytesExecutor(changed),
        _base_receipt(original),
    )
    assert receipt is not None and receipt.success is False
    assert receipt.failure_class == "integrity_violation"
    assert receipt.payload["native_primary_perception_status"] == "identity_mismatch"
    assert called is False


def test_unsupported_media_keeps_legacy_fallback_available() -> None:
    raw = b"pdf"
    receipt = stage_same_primary_native_image(
        SimpleNamespace(active_hooks=SimpleNamespace(stage_primary_native_image_observation=lambda **_: True)),
        SimpleNamespace(action_id="inspect"),
        1,
        _BytesExecutor(raw),
        _base_receipt(raw, media_type="application/pdf", path="x.pdf"),
    )
    assert receipt is None


def test_native_image_size_bound_fails_honestly_before_staging() -> None:
    raw = b"x" * (MAX_NATIVE_IMAGE_BYTES + 1)
    called = False

    def stage(**_kwargs: object) -> bool:
        nonlocal called
        called = True
        return True

    receipt = stage_same_primary_native_image(
        SimpleNamespace(active_hooks=SimpleNamespace(stage_primary_native_image_observation=stage)),
        SimpleNamespace(action_id="inspect"),
        1,
        _BytesExecutor(raw),
        _base_receipt(raw),
    )
    assert receipt is not None and receipt.success is False
    assert receipt.payload["native_primary_perception_status"] == "artifact_too_large"
    assert called is False


def test_provider_native_stage_requires_committed_previous_response_parent() -> None:
    raw = b"pixels"
    model, _client = _model([_response(1)])
    assert model.stage_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_path="image.png",
        source_receipt_id="r1",
        run_id="run-a",
        task_id="task-a",
    ) is False


def test_same_primary_request_pairs_exact_pixels_with_unchanged_text_boundary() -> None:
    raw = b"\x89PNG\r\n\x1a\nsynthetic-exact-pixels"
    digest = hashlib.sha256(raw).hexdigest()
    model, client = _model([_response(1), _response(2)])
    _call(model, "first")
    assert model.stage_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=digest,
        artifact_path="image.png",
        source_receipt_id="inspect:r1",
        run_id="run-a",
        task_id="task-a",
    ) is True
    _call(model, "second")

    second = client.responses.requests[1]
    assert second["previous_response_id"] == "resp-1"
    [tool_output] = second["input"]  # type: ignore[index]
    assert tool_output["type"] == "function_call_output"
    assert tool_output["call_id"] == "call-1"
    output = tool_output["output"]
    assert isinstance(output, list) and len(output) == 2
    expected_boundary = json.dumps(
        [{"role": "user", "content": "second"}],
        sort_keys=True,
        separators=(",", ":"),
    )
    assert output[0] == {"type": "input_text", "text": expected_boundary}
    assert output[1]["type"] == "input_image"
    prefix = "data:image/png;base64,"
    assert output[1]["image_url"].startswith(prefix)
    assert base64.b64decode(output[1]["image_url"][len(prefix):]) == raw

    events = [row for row in model.drain_telemetry() if row.get("event_kind") == "provider_attempt"]
    second_event = events[1]
    assert second_event["pcr_native_image_observation_count"] == 1
    assert second_event["pcr_native_image_artifact_sha256"] == digest
    assert second_event["pcr_native_image_artifact_bytes"] == len(raw)
    assert second_event["pcr_native_image_raw_bytes_persisted_in_telemetry"] is False
    assert second_event["pcr_continuity_current_boundary_function_output_match_count"] == 1
    event_text = json.dumps(second_event, sort_keys=True, default=str)
    assert base64.b64encode(raw).decode("ascii") not in event_text


def test_rejected_candidate_preserves_image_but_commit_consumes_exactly_once() -> None:
    raw = b"pixels-for-retry"
    digest = hashlib.sha256(raw).hexdigest()
    model, client = _model([_response(1), _response(2), _response(3), _response(4)])
    _call(model, "first")
    assert model.stage_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=digest,
        artifact_path="image.png",
        source_receipt_id="inspect:r1",
        run_id="run-a",
        task_id="task-a",
    ) is True

    _call(model, "candidate", commit=False)
    model.reject_pending_response(run_id="run-a", task_id="task-a")
    _call(model, "correction", commit=False)
    second_output = client.responses.requests[1]["input"][0]["output"]  # type: ignore[index]
    third_output = client.responses.requests[2]["input"][0]["output"]  # type: ignore[index]
    assert isinstance(second_output, list)
    assert isinstance(third_output, list)
    assert second_output[1]["image_url"] == third_output[1]["image_url"]
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"
    assert client.responses.requests[2]["previous_response_id"] == "resp-1"

    model.commit_pending_response(run_id="run-a", task_id="task-a")
    _call(model, "after-commit")
    fourth_output = client.responses.requests[3]["input"][0]["output"]  # type: ignore[index]
    assert isinstance(fourth_output, str)
    admissions = model.drain_continuity_admission_telemetry()
    assert [row["pcr_continuity_parent_disposition"] for row in admissions] == [
        "committed", "rejected", "committed", "committed",
    ]
    assert admissions[1].get("pcr_native_image_observation_consumed") is None
    assert admissions[2]["pcr_native_image_observation_consumed"] is True
    assert admissions[3]["pcr_native_image_observation_consumed"] is False


def test_scope_cleanup_releases_unconsumed_native_image() -> None:
    raw = b"pixels"
    model, client = _model([_response(1), _response(2)])
    _call(model, "first")
    assert model.stage_native_image_observation(
        image_bytes=raw,
        media_type="image/png",
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        artifact_path="image.png",
        source_receipt_id="r1",
        run_id="run-a",
        task_id="task-a",
    ) is True
    model.clear_continuity_scope(run_id="run-a", task_id="task-a")
    _call(model, "fresh")
    assert "previous_response_id" not in client.responses.requests[1]




def test_dispatch_prefers_same_primary_native_image_over_legacy_caption_model() -> None:
    raw = b"image-bytes"
    identity = _image_identity(raw)
    legacy_called = False
    native_rows: list[dict[str, object]] = []

    class Perception:
        def inspect(self, *_args: object, **_kwargs: object) -> Receipt:
            return Receipt(
                receipt_id="step-1:img:inspect",
                step=1,
                kind="artifact_inspection",
                success=False,
                summary="metadata only",
                failure_class="perception_required",
                payload={
                    "path": "image.png",
                    "mode": "image",
                    "metadata": {
                        "artifact_identity": identity,
                        "semantic_content_available": False,
                    },
                },
            )

    def native(**kwargs: object) -> bool:
        native_rows.append(dict(kwargs))
        return True

    def legacy(*_args: object, **_kwargs: object) -> str:
        nonlocal legacy_called
        legacy_called = True
        raise AssertionError("legacy caption route must not run")

    kernel = SimpleNamespace(
        perception_lane=Perception(),
        active_hooks=SimpleNamespace(
            stage_primary_native_image_observation=native,
            perceive_image=legacy,
        ),
    )
    action = ActionRequest(
        "img", "inspect_artifact", "artifact_inspection",
        {"path": "image.png", "mode": "image"},
        "inspect", "pixels", "fallback",
    )
    rows = dispatch_action(
        kernel,
        action,
        1,
        SimpleNamespace(),
        _BytesExecutor(raw),
        EnvMap(task_prompt="see image", workspace_root="/app"),
        ExecutionLedger(),
    )
    assert len(rows) == 1 and rows[0].success is True
    assert rows[0].payload["extraction_route"] == "same_primary_native_image"
    assert native_rows and native_rows[0]["image_bytes"] == raw
    assert legacy_called is False


def test_native_image_support_does_not_add_model_facing_tool() -> None:
    assert "inspect_artifact" in FIXED_KERNEL_TOOL_SURFACE
    assert "perceive_image" not in FIXED_KERNEL_TOOL_SURFACE
    assert "native_image" not in FIXED_KERNEL_TOOL_SURFACE


def test_inspect_artifact_provider_schema_discloses_same_primary_image_perception() -> None:
    schema = pcr_primary_turn_schema()
    rendered = json.dumps(schema, sort_keys=True)
    assert "same-Primary native image perception" in rendered
    assert "observation, not automatic proof" in rendered
