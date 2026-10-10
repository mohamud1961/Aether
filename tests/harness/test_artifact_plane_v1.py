from __future__ import annotations

from pathlib import Path

from aether.artifact_plane import derive_bytes, exact_capture, identify_bytes, identify_file
from aether.execution import ActionRequest, PerceptionLane
from aether.real_executor import SubprocessExecutor


def test_exact_artifact_identity_is_content_addressed_and_media_typed(tmp_path: Path) -> None:
    path = tmp_path / "report.pdf"
    path.write_bytes(b"%PDF-1.7\nexact-bytes\n")
    identity = identify_file(path, logical_path="report.pdf", source="test")
    assert identity.bytes == len(path.read_bytes())
    assert identity.media_type == "application/pdf"
    assert identity.handle == f"artifact:sha256:{identity.sha256}"
    assert identity.as_dict()["handle"] == identity.handle


def test_derivative_binds_source_hash_transform_version_and_exact_parameters() -> None:
    source = identify_bytes(b"source", path="document.pdf", media_type="application/pdf")
    derivation = derive_bytes(
        source,
        b"rendered-page-pixels",
        derivative_path="page-3.png",
        derivative_media_type="image/png",
        transform="pdf_page_render",
        transform_version="renderer-x:1.4.2",
        parameters={"page": 3, "dpi": 144},
        generation="g7",
        captured_at="2026-08-20T00:00:00+00:00",
    )
    row = derivation.as_dict()
    assert row["source"]["sha256"] == source.sha256
    assert row["derivative"]["sha256"] != source.sha256
    assert row["transform"] == "pdf_page_render"
    assert row["transform_version"] == "renderer-x:1.4.2"
    assert row["parameters"] == {"dpi": 144, "page": 3}
    assert row["generation"] == "g7"
    assert len(row["derivation_sha256"]) == 64


def test_exact_screenshot_capture_records_live_surface_without_claiming_repeatability() -> None:
    capture = exact_capture(
        b"PNG-PIXELS",
        surface="qemu-vnc:5900",
        dimensions=(1280, 720),
        region={"x": 10, "y": 20, "width": 100, "height": 80},
        capture_backend="vnc-screenshot",
        capture_backend_version="2.1",
        generation="vm-generation-3",
        captured_at="2026-08-20T00:01:02+00:00",
    )
    row = capture.as_dict()
    assert row["transform"] == "exact_screen_capture"
    assert row["source"]["media_type"] == "application/x-aether-live-surface"
    assert row["derivative"]["media_type"] == "image/png"
    assert row["parameters"]["surface"] == "qemu-vnc:5900"
    assert row["parameters"]["dimensions"] == [1280, 720]
    assert row["captured_at"] == "2026-08-20T00:01:02+00:00"


def test_subprocess_artifact_inspection_always_exposes_exact_identity(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello artifact\n", encoding="utf-8")
    executor = SubprocessExecutor(str(tmp_path))
    inspection = executor.inspect_artifact("note.txt", "text")
    assert inspection.success is True
    identity = inspection.metadata["artifact_identity"]
    assert identity["handle"] == inspection.metadata["artifact_handle"]
    assert identity["sha256"] == inspection.metadata["sha256"]
    assert identity["bytes"] == len(b"hello artifact\n")
    assert identity["media_type"] == "text/plain"


def test_perception_receipt_projects_identity_but_does_not_replace_artifact_authority(tmp_path: Path) -> None:
    (tmp_path / "data.json").write_text('{"value": 7}\n', encoding="utf-8")
    executor = SubprocessExecutor(str(tmp_path))
    action = ActionRequest(
        action_id="a1",
        kind="inspect_artifact",
        capability_id="artifact",
        arguments={"path": "data.json", "mode": "json"},
        intent="",
        expected_observation="",
        if_fail_next="",
    )
    receipt = PerceptionLane().inspect(action, 1, executor, workspace_root=str(tmp_path))
    assert receipt.success is True
    assert receipt.payload["artifact_handle"].startswith("artifact:sha256:")
    assert receipt.payload["artifact_identity"]["sha256"] == receipt.payload["metadata"]["sha256"]
    assert receipt.payload["extracted_text"] == '{"value": 7}\n'
