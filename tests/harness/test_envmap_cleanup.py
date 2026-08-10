from __future__ import annotations

from pathlib import Path

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.envmap_builder import build_envmap_from_task
from aether.kernel_messages import build_architect_request
from aether.task_capability import classify_capability_needs


def _caps(text: str, *, files: tuple[str, ...] = ()) -> set[str]:
    return {need.capability for need in classify_capability_needs(text, visible_files=files)}


def test_capability_inference_uses_tokens_not_substrings() -> None:
    assert "background_service" not in _caps("Write a report summarizing date ranges.")
    assert "background_service" not in _caps("The image has a blurred background.")
    assert "scientific_computing" not in _caps("Return every university instance.")
    assert "binary_reverse_engineering" not in _caps("Create a self-signed certificate.")


def test_capability_inference_keeps_real_visible_requirements() -> None:
    assert "background_service" in _caps("Start a server that listens for requests.")
    assert "scientific_computing" in _caps("Fit Raman peaks using scipy.")
    assert "binary_reverse_engineering" in _caps("Extract strings from this ELF binary.")
    assert "media_transcode" in _caps("Find the jump frame in the MP4 video.")


def test_architect_request_excludes_benchmark_metadata_but_keeps_visible_surfaces(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Run `pytest` to check.\n")
    (tmp_path / "test_app.py").write_text("def test_x(): pass\n")
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Fix the app. Run `pytest` if useful.",
        task_toml={
            "metadata": {
                "category": "security",
                "difficulty": "hard",
                "tags": ["benchmark-tag"],
                "expert_time_estimate_min": 20,
            },
            "agent": {"timeout_sec": 900},
            "verifier": {"timeout_sec": 120},
            "environment": {"docker_image": "private/image:latest", "cpus": 4},
        },
    )
    request = build_architect_request(envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)))
    task = request["task"]
    environment = request["environment"]
    encoded = str(request)

    assert request["schema_version"] == "architect_request.v2"
    assert "category" not in encoded
    assert "difficulty" not in encoded
    assert "benchmark-tag" not in encoded
    assert "docker_image" not in encoded
    assert "public_task_metadata" not in encoded
    assert "internal_task_metadata" not in encoded
    assert environment["resource_limits"]["agent_timeout_sec"] == 900
    assert task["visible_materials"]["validation_candidates"]
    assert "summary" in task["visible_materials"]
    assert "task_capability_requirements" not in encoded
    assert "instruction_tool_hints" not in encoded
    assert "instruction_language_hints" not in encoded
    assert environment["capability_availability"]
    assert "observed_support" in environment
    assert "reviewer_support" in environment


def test_envmap_exposes_media_facts_without_task_family_strategy(tmp_path: Path) -> None:
    (tmp_path / "video.mp4").write_bytes(b"fake")
    envmap = build_envmap_from_task(str(tmp_path), "Find the takeoff frame in the video.")
    request = build_architect_request(envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)))

    assert "task_capability_requirements" not in str(request)
    assert "capability_requirements" not in envmap.task_metadata
    assets = request["task"]["visible_materials"]["declared_assets"]
    assert any(item["path"] == "video.mp4" and item["mime_type"] == "video/mp4" for item in assets)
    assert all("strategy" not in str(item).lower() for item in assets)
    tools = {
        tool
        for capability in request["environment"]["capability_availability"]
        for tool in capability["tools"]
    }
    assert "run_command" in tools
    assert request["environment"]["reviewer_support"]["can_read_files"] is True


def test_architect_request_contains_no_prompt_derived_tool_or_language_strategy(tmp_path: Path) -> None:
    (tmp_path / "input.gcode").write_text("G1 X0 Y0\n", encoding="utf-8")
    envmap = build_envmap_from_task(
        str(tmp_path),
        "Use Python and ffmpeg to inspect the G-code and create /app/out.txt.",
    )
    request = build_architect_request(envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)))
    serialized = str(request)
    assert "task_capability_requirements" not in serialized
    assert "required_tool_hints" not in serialized
    assert "instruction_tool_hints" not in serialized
    assert "instruction_language_hints" not in serialized
    assert request["task"]["path_facts"]["instruction_output_paths"] == ["/app/out.txt"]


def test_timeout_budget_does_not_create_semantic_long_running_requirement() -> None:
    caps = _caps("Write /app/output.txt with hello.")
    assert "long_running_command" not in caps


def test_high_recall_capability_families_are_visible_but_evidence_backed() -> None:
    assert "text_log_data_transformation" in _caps("Summarize counts from CSV logs by date range.")
    assert "query_semantic_data" in _caps("Write a SPARQL query over an RDF Turtle graph.")
    assert "git_repository_repair" in _caps("Recover the lost commit from the git repository.")
    assert "web_security_sanitization" in _caps("Sanitize HTML and remove javascript: XSS payloads.")
    assert "password_hash_secret_recovery" in _caps("Recover the password from this 7z hash.")
    assert "geometry_toolpath_extraction" in _caps("Read the G-code toolpath and extract the text from printer moves.")


def test_server_word_alone_is_not_background_service() -> None:
    assert "background_service" not in _caps("Review the server support notes in the README.")
    assert "background_service" in _caps("Start a server that listens for requests.")


def test_reviewer_probe_support_uses_inspector_surface_not_only_envmap_caps(tmp_path: Path) -> None:
    envmap = build_envmap_from_task(str(tmp_path), "Create /app/output.txt")
    request = build_architect_request(envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)))
    support = request["environment"]["reviewer_support"]
    assert support["can_read_files"] is True
    assert support["can_read_output_handles"] is True
    assert support["can_inspect_artifacts"] is True
    assert support["source"] == "verifier_inspector_schema_and_live_probe_tools"
