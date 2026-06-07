from __future__ import annotations

import json
from pathlib import Path

from tools import run_active_evidence_kernel_health_gate as mod


def test_health_gate_fails_closed_when_azure_route_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mod,
        "detect_azure_openai_routes",
        lambda: {
            "routes": [
                {
                    "available": False,
                    "missing_envs": ["AZURE_OPENAI_GPT54_MINI_KEY"],
                    "checked_env_groups": {"AZURE_OPENAI_GPT54_MINI_KEY": ["AZURE_OPENAI_GPT54_MINI_KEY"]},
                }
            ]
        },
    )

    payload = mod.run_active_evidence_kernel_health_gate(output_root=tmp_path, sandbox_type="none")

    assert payload["status"] == "invalid_due_to_environment"
    assert payload["reason_code"] == "invalid_due_to_environment_missing_azure_gpt54_mini_route"
    run_root = Path(payload["run_root"])
    assert json.loads((run_root / "health_gate.json").read_text(encoding="utf-8"))["status"] == "invalid_due_to_environment"


def test_health_gate_reports_healthy_after_completion_and_tool_smoke(tmp_path, monkeypatch):
    monkeypatch.setattr(
        mod,
        "detect_azure_openai_routes",
        lambda: {"routes": [{"available": True, "missing_envs": [], "checked_env_groups": {}}]},
    )
    monkeypatch.setattr(mod, "make_azure_gpt54_mini_route_from_env", lambda **_: {"provider_route": "openai_api"})

    class _HealthyClient:
        def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            return {"text": "HEALTH_OK", "tool_calls": []}

    monkeypatch.setattr(mod, "make_model_client_from_route", lambda *args, **kwargs: _HealthyClient())

    def fake_run_reference_baseline(**kwargs):  # type: ignore[no-untyped-def]
        workspace = Path(kwargs["cwd"])
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "health_gate_artifact.txt").write_text("KERNEL_HEALTH_OK\n", encoding="utf-8")
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "event_type": "model_completion",
                "payload": {"details": {"tool_call_count": 1}},
            },
            {"event_type": "raw_bash_result", "payload": {"details": {}}},
            {"event_type": "evidence_kernel_receipt", "payload": {"details": {}}},
        ]
        (run_dir / "run_events.jsonl").write_text(
            "\n".join(json.dumps(event) for event in events) + "\n",
            encoding="utf-8",
        )
        return {"run_events": events}

    monkeypatch.setattr(mod, "run_reference_baseline", fake_run_reference_baseline)

    payload = mod.run_active_evidence_kernel_health_gate(output_root=tmp_path, sandbox_type="none")

    assert payload["status"] == "healthy"
    assert payload["healthy"] is True
    assert payload["active_kernel_smoke"]["tool_call_count"] == 1
