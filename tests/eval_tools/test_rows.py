"""Trial-row validity tests. Ported from the source tree's row-validity class (assertions kept)."""

from __future__ import annotations

from harness_evals.rows import annotate_rows, classify_row_validity, compute_validity_summary


class TestRowValidity:
    def test_backend_error_marks_invalid(self) -> None:
        row = {"task": "demo", "condition": "off", "reason_code": "harbor_native_backend_error", "model_calls": None}
        result = classify_row_validity(row)
        assert result["row_validity"] == "invalid"
        assert result["invalid_reason"] == "backend_failure_before_model_work"
        assert result["exclude_from_ab"] is True
        assert result["model_work_started"] is False

    def test_null_model_calls_marks_invalid(self) -> None:
        row = {"task": "demo", "condition": "off", "model_calls": None}
        result = classify_row_validity(row)
        assert result["row_validity"] == "invalid"
        assert result["invalid_reason"] == "no_model_calls"

    def test_zero_model_calls_marks_invalid(self) -> None:
        row = {"task": "demo", "condition": "off", "model_calls": 0}
        result = classify_row_validity(row)
        assert result["row_validity"] == "invalid"
        assert result["invalid_reason"] == "no_model_calls"

    def test_positive_model_calls_valid(self) -> None:
        row = {"task": "demo", "condition": "off", "model_calls": 5, "mean": 0.0}
        result = classify_row_validity(row)
        assert result["row_validity"] == "valid"
        assert result["invalid_reason"] is None
        assert result["exclude_from_ab"] is False
        assert result["model_work_started"] is True

    def test_reward_positive_unknown_ownership_stays_valid(self) -> None:
        """Reward-positive with unknown ownership must NOT be marked invalid."""
        row = {"task": "service-task", "condition": "on", "model_calls": 10, "mean": 1.0}
        result = classify_row_validity(row)
        assert result["row_validity"] == "valid"
        assert result["ownership"] == "unknown"

    def test_reward_positive_contradicted_ownership_invalid(self) -> None:
        row = {
            "task": "service-task",
            "condition": "on",
            "model_calls": 10,
            "mean": 1.0,
            "remote_workspace_root": "/app",
            "status_path": "/tmp/jobs/run/status.json",
            "finalize_reason": "port_never_bound",
        }
        result = classify_row_validity(row)
        assert result["row_validity"] == "contaminated"
        assert result["invalid_reason"] == "reward_positive_ownership_contradicted"
        assert result["ownership"] == "contradicted"
        assert result["exclude_from_ab"] is True

    def test_reward_positive_confirmed_ownership_stays_valid(self) -> None:
        row = {
            "task": "service-task",
            "model_calls": 10,
            "mean": 1.0,
            "remote_workspace_root": "/app",
            "status_path": "/tmp/status.json",
            "finalize_reason": "service_owned",
        }
        result = classify_row_validity(row)
        assert result["row_validity"] == "valid"
        assert result["ownership"] == "confirmed"

    def test_provider_preflight_failure_marks_invalid(self) -> None:
        row = {
            "task": "demo",
            "condition": "receipt_driven_full",
            "provider_preflight_status": "preflight_failed",
            "model_calls": None,
        }
        result = classify_row_validity(row)
        assert result["row_validity"] == "invalid"
        assert result["invalid_reason"] == "provider_preflight_failed"
        assert result["provider_preflight_status"] == "preflight_failed"

    def test_annotate_rows_adds_fields(self) -> None:
        rows = [{"task": "a", "model_calls": 5}, {"task": "b", "model_calls": None}]
        annotated = annotate_rows(rows)
        assert len(annotated) == 2
        assert annotated[0]["row_validity"] == "valid"
        assert annotated[1]["row_validity"] == "invalid"

    def test_annotate_never_drops_or_replaces_rows(self) -> None:
        rows = [{"task": "a", "model_calls": None}, {"task": "b", "model_calls": 3}]
        annotated = annotate_rows(rows)
        assert [r["task"] for r in annotated] == ["a", "b"]
        assert annotated[0]["exclude_from_ab"] is True

    def test_compute_validity_summary(self) -> None:
        rows = [
            {"row_validity": "valid", "invalid_reason": None},
            {"row_validity": "invalid", "invalid_reason": "no_model_calls"},
            {"row_validity": "invalid", "invalid_reason": "no_model_calls"},
            {"row_validity": "contaminated", "invalid_reason": "reward_positive_ownership_contradicted"},
        ]
        summary = compute_validity_summary(rows)
        assert summary["total_rows"] == 4
        assert summary["valid_rows"] == 1
        assert summary["invalid_rows"] == 2
        assert summary["contaminated_rows"] == 1
        assert summary["invalid_reasons"]["no_model_calls"] == 2
        assert summary["invalid_reasons"]["reward_positive_ownership_contradicted"] == 1
