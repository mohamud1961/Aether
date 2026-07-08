from __future__ import annotations

from pathlib import Path

from aether_next.compiler import CapabilityRegistry, ConfigCompiler
from aether_next.envmap_builder import build_envmap_from_task
from aether_next.kernel_messages import build_architect_request
from aether_next.task_capability import classify_capability_needs


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
    assert "video_processing" in _caps("Find the jump frame in the MP4 video.")


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
    model_env = request["envmap"]
    metadata = model_env["task_metadata"]

    assert "category" not in metadata
    assert "difficulty" not in metadata
    assert "tags" not in metadata
    assert "docker_image" not in str(model_env)
    assert "public_task_metadata" not in metadata
    assert "internal_task_metadata" not in metadata
    assert metadata["agent_timeout_sec"] == 900
    assert model_env["visible_task_materials"]["visible_validation_surfaces"]
    assert "visible_material_summary" in model_env["visible_task_materials"]
    assert isinstance(model_env["task_capability_requirements"], list)
    assert model_env["available_action_affordances"]
    assert "observed_environment_support" in model_env
    assert "reviewer_probe_support" in model_env


def test_envmap_layers_mark_requirements_as_inferred_not_availability(tmp_path: Path) -> None:
    (tmp_path / "video.mp4").write_bytes(b"fake")
    envmap = build_envmap_from_task(str(tmp_path), "Find the takeoff frame in the video.")
    request = build_architect_request(envmap, ConfigCompiler(CapabilityRegistry.from_envmap(envmap)))
    model_env = request["envmap"]

    reqs = model_env["task_capability_requirements"]
    assert any(req["capability"] == "video_processing" for req in reqs)
    assert all(req["inferred_not_fact"] is True for req in reqs)
    assert any(item["action"] == "run_command" for item in model_env["available_action_affordances"])
    assert model_env["reviewer_probe_support"]["can_read_files"] is True


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
    support = request["envmap"]["reviewer_probe_support"]
    assert support["can_read_files"] is True
    assert support["can_read_output_handles"] is True
    assert support["can_inspect_artifacts"] is True
    assert support["source"] == "verifier_inspector_schema_and_live_probe_tools"
