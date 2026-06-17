from __future__ import annotations

import hashlib
import json
from pathlib import Path

from runner.kernel_artifacts import (
    build_artifact_inspection_receipt_payload,
    build_artifact_record,
    check_required_artifacts,
    classify_artifact_command,
    extract_artifact_path_refs,
    guess_artifact_type,
    refresh_artifact_registry,
    summarize_artifact_registry,
)


def test_guess_artifact_type_is_conservative_and_suffix_driven():
    assert guess_artifact_type(Path("notes.txt"))["type_guess"] == "text"
    assert guess_artifact_type(Path("payload.json"))["type_guess"] == "json"
    assert guess_artifact_type(Path("table.csv"))["type_guess"] == "csv"
    assert guess_artifact_type(Path("archive.tar.gz"))["type_guess"] == "archive"
    assert guess_artifact_type(Path("slide.pdf"))["type_guess"] == "document"
    assert guess_artifact_type(Path("image.png"))["type_guess"] == "image"
    assert guess_artifact_type(Path("clip.mp4"))["type_guess"] == "video"
    assert guess_artifact_type(Path("audio.wav"))["type_guess"] == "audio"
    assert guess_artifact_type(Path("mystery.weird"))["type_guess"] == "unknown"


def test_extract_artifact_path_refs_skips_heredoc_noise_and_returns_real_paths():
    command = (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "payload = 'x' * 4096\n"
        "Path('candidate/readiness_receipt.json').write_text('{\"ok\": true}\\n')\n"
        "PY"
    )

    refs = extract_artifact_path_refs(command)

    assert refs == ["candidate/readiness_receipt.json"]


def test_build_artifact_record_normalizes_paths_hashes_and_marks_freshness(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "artifacts" / "report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{\"ok\": true}\n", encoding="utf-8")

    record = build_artifact_record(
        path=Path("artifacts/report.json"),
        workspace_root=workspace,
        origin_receipt_id="r0001",
        generated=False,
    )

    expected_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert record["path"] == "artifacts/report.json"
    assert record["exists"] is True
    assert record["size_bytes"] == artifact.stat().st_size
    assert record["sha256"] == expected_sha256
    assert record["suffix"] == ".json"
    assert record["type_guess"] == "json"
    assert record["origin_receipt_id"] == "r0001"
    assert record["last_seen_receipt_id"] == "r0001"
    assert record["generated"] is False
    assert record["freshness"] == "original"


def test_refresh_artifact_registry_ignores_unsafe_command_text_candidates_and_keeps_safe_paths(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report = workspace / "candidate" / "result.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{\"ok\": true}\n", encoding="utf-8")
    unsafe_command = (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "Path('candidate/result.json').write_text('{\"ok\": true}\\n')\n"
        "PY"
    )

    refreshed = refresh_artifact_registry(
        workspace_root=workspace,
        existing={},
        candidate_paths=[unsafe_command, "candidate/result.json"],
        receipt_id="r0001",
    )

    assert set(refreshed) == {"candidate/result.json"}
    assert refreshed["candidate/result.json"]["exists"] is True
    assert refreshed["candidate/result.json"]["freshness"] == "generated"


def test_refresh_artifact_registry_tracks_generated_modified_and_missing_paths(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report = workspace / "artifacts" / "report.txt"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("old\n", encoding="utf-8")

    original_record = build_artifact_record(
        path=Path("artifacts/report.txt"),
        workspace_root=workspace,
        origin_receipt_id="r0001",
        generated=False,
    )

    report.write_text("new\n", encoding="utf-8")
    refreshed = refresh_artifact_registry(
        workspace_root=workspace,
        existing={"artifacts/report.txt": original_record},
        candidate_paths=["artifacts/report.txt", "artifacts/missing.bin"],
        receipt_id="r0002",
    )

    modified = refreshed["artifacts/report.txt"]
    missing = refreshed["artifacts/missing.bin"]
    assert modified["freshness"] == "modified"
    assert modified["origin_receipt_id"] == "r0001"
    assert modified["last_seen_receipt_id"] == "r0002"
    assert modified["generated"] is True
    assert missing["exists"] is False
    assert missing["freshness"] == "missing"
    assert missing["last_seen_receipt_id"] == "r0002"


def test_check_required_artifacts_marks_unsafe_command_text_missing_with_placeholder(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    report = workspace / "final" / "report.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("{\"status\": \"pass\"}\n", encoding="utf-8")
    unsafe_command = (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "Path('candidate/readiness_receipt.json').write_text('{\"ok\": true}\\n')\n"
        "PY"
    )

    result = check_required_artifacts(
        workspace_root=workspace,
        required_paths=[unsafe_command, "final/report.json"],
    )

    assert result["status"] == "fail"
    assert result["reason_codes"] == ["required_artifact_missing"]
    assert result["required_paths"][0].startswith("<invalid_artifact_path_ref:")
    assert result["missing_paths"][0].startswith("<invalid_artifact_path_ref:")
    assert result["required_paths"][1] == "final/report.json"
    assert result["observed_hashes"]["final/report.json"] == hashlib.sha256(report.read_bytes()).hexdigest()
    assert "python3" not in result["required_paths"][0]


def test_summarize_artifact_registry_groups_records_by_type_and_freshness(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("hello\n", encoding="utf-8")
    (workspace / "clip.mp4").write_bytes(b"mp4")

    registry = {
        "notes.txt": build_artifact_record(
            path=Path("notes.txt"),
            workspace_root=workspace,
            origin_receipt_id="r0001",
            generated=False,
        ),
        "clip.mp4": build_artifact_record(
            path=Path("clip.mp4"),
            workspace_root=workspace,
            origin_receipt_id="r0002",
            generated=True,
        ),
        "missing.json": build_artifact_record(
            path=Path("missing.json"),
            workspace_root=workspace,
            origin_receipt_id=None,
            generated=False,
        ),
    }

    summary = summarize_artifact_registry(registry)

    assert summary["artifact_count"] == 3
    assert summary["type_counts"] == {"json": 1, "text": 1, "video": 1}
    assert summary["freshness_counts"] == {"generated": 1, "missing": 1, "original": 1}
    assert summary["original_artifacts"] == ["notes.txt"]
    assert summary["generated_artifacts"] == ["clip.mp4"]
    assert summary["missing_artifacts"] == ["missing.json"]
    assert {item["path"] for item in summary["recent_artifacts"]} == {"notes.txt", "clip.mp4", "missing.json"}


def test_classify_artifact_command_uses_generic_operation_families():
    assert classify_artifact_command("find . -type f")["kind"] == "artifact_discovery"
    assert classify_artifact_command("cat artifacts/report.json")["kind"] == "artifact_read"
    assert classify_artifact_command("sha256sum artifacts/report.json")["kind"] == "artifact_verify"
    assert classify_artifact_command("python3 -c \"Path('out.txt').write_text('x')\"")["kind"] == "artifact_transform"
    assert classify_artifact_command("git status")["kind"] == "artifact_other"


def test_build_artifact_inspection_receipt_payload_includes_registry_summary_and_raw_refs(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    registry = {
        "report.json": build_artifact_record(
            path=Path("report.json"),
            workspace_root=workspace,
            origin_receipt_id="r0001",
            generated=False,
        ),
        "notes.txt": build_artifact_record(
            path=Path("notes.txt"),
            workspace_root=workspace,
            origin_receipt_id=None,
            generated=False,
        ),
    }

    payload = build_artifact_inspection_receipt_payload(
        command="cat report.json",
        receipt={"receipt_id": "r0002", "action_id": "a0002", "action_type": "command", "reason_code": "tool_success"},
        registry=registry,
    )

    assert payload["receipt_id"] == "r0002"
    assert payload["action_id"] == "a0002"
    assert payload["command_classification"]["kind"] == "artifact_read"
    assert payload["artifact_registry_summary"]["artifact_count"] == 2
    assert len(payload["artifact_refs"]) == 2
    assert {ref["path"] for ref in payload["artifact_refs"]} == {"report.json", "notes.txt"}


def test_check_required_artifacts_passes_for_non_empty_files(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    final_report = workspace / "final" / "report.json"
    final_report.parent.mkdir(parents=True, exist_ok=True)
    final_report.write_text("{\"status\": \"pass\"}\n", encoding="utf-8")

    result = check_required_artifacts(
        workspace_root=workspace,
        required_paths=["final/report.json"],
    )

    assert result["status"] == "pass"
    assert result["reason_codes"] == []
    assert result["missing_paths"] == []
    assert result["empty_paths"] == []
    assert result["observed_hashes"]["final/report.json"] == hashlib.sha256(final_report.read_bytes()).hexdigest()


def test_check_required_artifacts_reports_missing_and_empty_files(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    empty_report = workspace / "final" / "empty.txt"
    empty_report.parent.mkdir(parents=True, exist_ok=True)
    empty_report.write_text("", encoding="utf-8")

    result = check_required_artifacts(
        workspace_root=workspace,
        required_paths=["final/missing.txt", "final/empty.txt"],
    )

    assert result["status"] == "fail"
    assert result["reason_codes"] == ["required_artifact_missing", "required_artifact_empty"]
    assert result["missing_paths"] == ["final/missing.txt"]
    assert result["empty_paths"] == ["final/empty.txt"]
    assert "final/missing.txt" not in result["observed_hashes"]
    assert "final/empty.txt" not in result["observed_hashes"]


def test_kernel_artifact_integration(tmp_path: Path):
    from runner.kernel_state import KernelState
    from runner.active_evidence_kernel import ActiveEvidenceKernel, _sync_execution_artifact_gate_state
    from runner.kernel_context_pack import build_context_pack
    from runner.kernel_gates import finalize as finalize_governed_gate

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create dummy files
    (workspace / "notes.txt").write_text("initial contents\n", encoding="utf-8")
    (workspace / "empty.json").write_text("", encoding="utf-8")

    state = KernelState(
        run_id="run-01",
        task_id="task-01",
        workspace_root=workspace,
        cwd=str(workspace),
        task_prompt="find the report and verify it",
    )

    kernel = ActiveEvidenceKernel(
        state=state,
        route_manifest={"required_artifact_paths": ["notes.txt", "empty.json"]},
    )

    # 1. Test after_tool_result updates artifact registry
    res = kernel.after_tool_result(
        tool_call={"name": "raw_bash", "arguments": {"command": "cat notes.txt"}},
        tool_result={"exit_code": 0, "stdout": "initial contents\n", "reason_code": "tool_success"},
        cwd=str(workspace),
        action_id="action-01",
    )

    assert "notes.txt" in state.artifact_registry
    assert state.artifact_registry["notes.txt"]["exists"] is True
    assert state.artifact_registry["notes.txt"]["freshness"] == "generated"

    # Verify artifact_inspection payload is in receipt
    receipt = res["receipt"]
    assert "artifact_inspection" in receipt
    assert receipt["artifact_inspection"]["command_classification"]["kind"] == "artifact_read"

    # 2. Test build_context_pack contains artifact_registry_summary
    pack = build_context_pack(state)
    assert "artifact_registry_summary" in pack
    assert pack["artifact_registry_summary"]["artifact_count"] >= 1
    assert "notes.txt" in pack["artifact_registry_summary"]["generated_artifacts"]

    # 3. Test verifier gate/finalization logic maps empty files correctly
    _sync_execution_artifact_gate_state(state, workspace, ["notes.txt", "empty.json"])

    gate_res = finalize_governed_gate(
        execution_result={
            "status": "completed",
            "active_kernel_state": state.to_dict(),
        },
        workspace_state={
            "active_kernel_state": state.to_dict(),
            "required_artifact_paths": ["notes.txt", "empty.json"],
        }
    )

    assert gate_res["status"] == "artifact_gate_failed"
    assert "artifact_gate_failed" in gate_res["reason_codes"]
    assert "empty_paths" in state.artifact_gate
    assert "empty.json" in state.artifact_gate["empty_paths"]
