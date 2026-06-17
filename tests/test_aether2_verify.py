import json
from types import SimpleNamespace

from runner.aether2.verify import DiscrepancyReport, RequirementResult, replay_checks, verify_fresh_context


class FakeExecutor:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def run(self, cmd, timeout_sec, cwd):
        self.commands.append(cmd)
        return SimpleNamespace(
            exit_code=0,
            stdout=f"ran {cmd}",
            stderr="",
            cwd=cwd or "/tmp/work",
            duration_sec=0.2,
        )


class FakeModelClient:
    def __init__(self) -> None:
        self.messages = None

    def call(self, messages, tools, *, cache_prefix_len):
        self.messages = messages
        assert tools == []
        assert cache_prefix_len == 0
        return {
            "output_text": json.dumps(
                {
                    "requirements": [
                        {
                            "requirement": "artifact exists",
                            "verdict": "satisfied",
                            "evidence": "artifact.txt present",
                            "evidence_refs": ["workspace_diff"],
                        },
                        {
                            "requirement": "service alive",
                            "verdict": "unverifiable",
                            "evidence": "no service evidence",
                            "evidence_refs": ["claim"],
                        },
                    ],
                    "reason_codes": ["service_unverifiable"],
                    "summary": "Artifact looks good; service evidence is missing.",
                }
            )
        }


class StaticModelClient:
    def __init__(self, output_text):
        self.output_text = output_text

    def call(self, messages, tools, *, cache_prefix_len):
        assert tools == []
        assert cache_prefix_len == 0
        return {"output_text": self.output_text}


def _verify_with_output(output_text, *, checks_results=None, diff=None, claim=None):
    return verify_fresh_context(
        task="task",
        orientation={},
        diff=diff or {},
        claim=claim or {"summary": "done"},
        checks_results=checks_results or [],
        action_digest={},
        model_client=StaticModelClient(output_text),
    )


def test_replay_checks_replays_commands_through_executor() -> None:
    executor = FakeExecutor()

    results = replay_checks(["pwd", "ls"], executor)

    assert executor.commands == ["pwd", "ls"]
    assert results[0].command == "pwd"
    assert results[1].stdout == "ran ls"


def test_replay_checks_preserves_timeout_and_error_truthfulness() -> None:
    class TruthfulExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def run(self, cmd, timeout_sec, cwd):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    exit_code=1,
                    stdout="",
                    stderr="failed",
                    cwd="/tmp/work",
                    duration_sec=0.1,
                    timed_out=False,
                    error=SimpleNamespace(kind="nonzero_exit", reason_code="nonzero_exit"),
                )
            return SimpleNamespace(
                exit_code=124,
                stdout="",
                stderr="",
                cwd="/tmp/work",
                duration_sec=1.0,
                timed_out=True,
                error=SimpleNamespace(kind="timeout", reason_code="timeout"),
            )

    results = replay_checks(["false", "sleep 5"], TruthfulExecutor())

    assert results[0].exit_code == 1
    assert results[0].timed_out is False
    assert results[0].error_kind == "nonzero_exit"
    assert results[0].error_reason_code == "nonzero_exit"
    assert results[1].exit_code == 124
    assert results[1].timed_out is True
    assert results[1].error_kind == "timeout"
    assert results[1].error_reason_code == "timeout"


def test_verify_fresh_context_cleans_hidden_refs_and_avoids_transcript_injection() -> None:
    model_client = FakeModelClient()
    report = verify_fresh_context(
        task="complete the task",
        orientation={
            "cwd": "/tmp/work",
            "hidden_answer": "secret",
            "details": {
                "artifact": "artifact.txt",
                "transcript": "orientation transcript should not leak",
            },
        },
        diff={
            "artifact.txt": "sha",
            "grader_secret": "nope",
            "details": {
                "status": "clean",
                "transcript": "diff transcript should not leak",
            },
        },
        claim={
            "summary": "done",
            "expected_output": "hidden",
            "details": {
                "summary": "visible",
                "transcript": "claim transcript should not leak",
            },
        },
        checks_results=[
            SimpleNamespace(
                command="pwd",
                exit_code=0,
                stdout="ok",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.1,
                hidden_answer="check-secret",
                transcript="executor transcript should not leak",
                metadata={
                    "visible": "ok",
                    "transcript": "check transcript should not leak",
                },
            )
        ],
        action_digest={
            "commands": ["ls"],
            "full_transcript": "should stay out",
            "trail": {
                "visible": "yes",
                "nested_transcript": "digest transcript should not leak",
            },
        },
        model_client=model_client,
    )

    assert report.summary == "Artifact looks good; service evidence is missing."
    assert report.reason_codes == ("service_unverifiable",)
    assert report.requirements[0].verdict == "satisfied"
    assert report.requirements[0].evidence_strength == "weak"
    assert report.requirements[0].evidence_strength_reasons == ("existence_or_read_only_observation",)
    assert report.requirements[0].confidence == "medium"
    assert report.requirements[0].evidence_refs == ("workspace_diff",)
    assert report.requirements[1].unresolved is True
    payload = json.loads(model_client.messages[1]["content"])
    assert "hidden_answer" not in json.dumps(payload)
    assert "grader_secret" not in json.dumps(payload)
    assert "expected_output" not in json.dumps(payload)
    assert "check-secret" not in json.dumps(payload)
    assert "executor transcript should not leak" not in json.dumps(payload)
    assert "orientation transcript should not leak" not in json.dumps(payload)
    assert "diff transcript should not leak" not in json.dumps(payload)
    assert "claim transcript should not leak" not in json.dumps(payload)
    assert "check transcript should not leak" not in json.dumps(payload)
    assert "digest transcript should not leak" not in json.dumps(payload)
    assert '"full_transcript"' not in model_client.messages[1]["content"]
    assert "full_transcript" not in payload["action_digest"]
    assert payload["orientation"]["details"] == {"artifact": "artifact.txt"}
    assert payload["workspace_diff"]["details"] == {"status": "clean"}
    assert payload["claim"]["details"] == {"summary": "visible"}
    assert payload["checks_results"][0]["metadata"] == {"visible": "ok"}
    assert payload["action_digest"]["trail"] == {"visible": "yes"}


def test_verify_fresh_context_validates_report_schema() -> None:
    report = _verify_with_output('{"oops": true}')

    assert report.reason_codes == ("verifier_parse_failed", "verifier_schema_invalid")
    assert report.requirements[0].requirement == "verification_output_schema"
    assert report.requirements[0].verdict == "unverifiable"
    assert report.requirements[0].evidence_refs == ("verifier.raw_response", "verifier.parsed_output")
    assert "parse_or_schema_failure" in report.requirements[0].evidence_strength_reasons
    assert report.requirements[0].confidence == "high"
    assert report.has_discrepancies is True
    assert report.has_unresolved_gaps is True
    assert report.summary == "Verifier output could not be normalized to the required schema."


def test_verify_fresh_context_keeps_non_json_parse_failures_blocker_ready() -> None:
    report = _verify_with_output("not-json-at-all")

    assert report.reason_codes == ("verifier_parse_failed", "verifier_output_not_json")
    assert report.requirements[0].requirement == "verification_output_parse"
    assert report.requirements[0].verdict == "unverifiable"
    assert report.requirements[0].evidence_refs == ("verifier.raw_response",)
    assert "parse_or_schema_failure" in report.requirements[0].evidence_strength_reasons
    assert report.requirements[0].unresolved is True
    assert report.summary == "Verifier output could not be parsed."


def test_verify_fresh_context_surfaces_requirement_schema_issues_as_unresolved_findings() -> None:
    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "service remains available",
                        "verdict": "satisfied",
                        "evidence": "Port 8080 open.",
                        "evidence_refs": "checks_results[0]",
                    }
                ],
                "reason_codes": [],
                "summary": "claimed success",
            }
        )
    )

    assert report.reason_codes == ("verifier_parse_failed", "verifier_schema_invalid")
    unresolved_names = [item.requirement for item in report.unresolved_requirements]
    assert "verification_output_schema" in unresolved_names
    schema_requirement = next(
        item for item in report.unresolved_requirements if item.requirement == "verification_output_schema"
    )
    assert schema_requirement.evidence_refs == ("verifier.raw_response", "verifier.parsed_output")
    assert "requirements[0].evidence_refs must be a list" in schema_requirement.evidence
    assert schema_requirement.unresolved is True


def test_has_discrepancies_treats_unverifiable_and_unsatisfied_as_unresolved() -> None:
    report = DiscrepancyReport(
        requirements=(
            RequirementResult(requirement="r1", verdict="satisfied", evidence="e1"),
            RequirementResult(requirement="r2", verdict="unverifiable", evidence="e2"),
        ),
        reason_codes=(),
        summary="mostly fine",
        raw_response="{}",
    )
    assert report.has_discrepancies is True
    assert report.has_unresolved_gaps is True
    assert [item.requirement for item in report.unresolved_requirements] == ["r2"]

    report_bad = DiscrepancyReport(
        requirements=(
            RequirementResult(requirement="r1", verdict="satisfied", evidence="e1"),
            RequirementResult(requirement="r2", verdict="unsatisfied", evidence="e2"),
        ),
        reason_codes=(),
        summary="something wrong",
        raw_response="{}",
    )
    assert report_bad.has_discrepancies is True

    report_parse_failed = DiscrepancyReport(
        requirements=(
            RequirementResult(requirement="verification_output_parse", verdict="unverifiable", evidence="e"),
        ),
        reason_codes=("verifier_parse_failed",),
        summary="could not parse",
        raw_response="{}",
    )
    assert report_parse_failed.has_discrepancies is True


def test_verify_fresh_context_classifies_weak_and_strong_evidence() -> None:
    class EvidenceModelClient:
        def call(self, messages, tools, *, cache_prefix_len):
            assert tools == []
            assert cache_prefix_len == 0
            return {
                "output_text": json.dumps(
                    {
                        "requirements": [
                            {
                                "requirement": "tool import works without manual path edits",
                                "verdict": "satisfied",
                                "evidence": 'Ran python -c "import widget" after export PYTHONPATH=/tmp/app and command -v widget passed.',
                                "evidence_refs": ["checks_results[0]"],
                            },
                            {
                                "requirement": "result is correct end to end",
                                "verdict": "satisfied",
                                "evidence": "Provided check pytest -q exited 0, compared actual output to expected output, and parsed result.json before use.",
                                "evidence_refs": ["checks_results[1]", "workspace_diff"],
                            },
                        ],
                        "reason_codes": [],
                        "summary": "One requirement has weak proof; one has strong proof.",
                    }
                )
            }

    report = verify_fresh_context(
        task="complete the task",
        orientation={},
        diff={"result.json": "sha256:abc"},
        claim={"summary": "done"},
        checks_results=[
            SimpleNamespace(
                command='export PYTHONPATH=/tmp/app && python -c "import widget" && command -v widget',
                exit_code=0,
                stdout="widget",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.1,
            ),
            SimpleNamespace(
                command="pytest -q",
                exit_code=0,
                stdout="2 passed",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.3,
            ),
        ],
        action_digest={},
        model_client=EvidenceModelClient(),
    )

    weak_requirement, strong_requirement = report.requirements
    assert weak_requirement.evidence_strength == "weak"
    assert "command_presence_only" in weak_requirement.evidence_strength_reasons
    assert "import_only" in weak_requirement.evidence_strength_reasons
    assert "environment_or_path_mutation" in weak_requirement.evidence_strength_reasons
    assert weak_requirement.confidence == "high"
    assert weak_requirement.evidence_refs == ("checks_results[0]",)

    assert strong_requirement.evidence_strength == "strong"
    assert "clean_execution" in strong_requirement.evidence_strength_reasons
    assert "independent_value_or_invariant_comparison" in strong_requirement.evidence_strength_reasons
    assert "artifact_parse_and_use" in strong_requirement.evidence_strength_reasons
    assert "provided_checks_without_environment_hacks" in strong_requirement.evidence_strength_reasons
    assert strong_requirement.confidence == "high"
    assert strong_requirement.evidence_refs == ("checks_results[1]", "workspace_diff")


def test_verify_fresh_context_treats_startup_only_service_probes_as_weak() -> None:
    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "service stays available",
                        "verdict": "satisfied",
                        "evidence": (
                            "Port 8080 is listening, pid 1234 exists, and a startup probe curl request returned 200 once."
                        ),
                        "evidence_refs": ["checks_results[0]"],
                    }
                ],
                "reason_codes": [],
                "summary": "startup looked healthy",
            }
        ),
        checks_results=[
            SimpleNamespace(
                command="lsof -i :8080 && curl -sf http://127.0.0.1:8080/health",
                exit_code=0,
                stdout="LISTEN\nok",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.2,
            )
        ],
    )

    requirement = report.requirements[0]
    assert requirement.evidence_strength == "weak"
    assert "process_or_port_open_only" in requirement.evidence_strength_reasons
    assert "startup_probe_only" in requirement.evidence_strength_reasons
    assert "service_probe_without_survival_window" in requirement.evidence_strength_reasons
    assert "client_interaction" in requirement.evidence_strength_reasons


def test_verify_fresh_context_marks_bounded_survival_and_state_validation_as_strong() -> None:
    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "service remains available and keeps state",
                        "verdict": "satisfied",
                        "evidence": (
                            "Service stayed up over a 30s window, the same pid handled a second probe after 30s, "
                            "the probe ran from the same workspace root using the project client, and the response matched expected state persisted value."
                        ),
                        "evidence_refs": ["checks_results[0]", "checks_results[1]"],
                    }
                ],
                "reason_codes": [],
                "summary": "service evidence is durable",
            }
        ),
        checks_results=[
            SimpleNamespace(
                command="./bin/client status",
                exit_code=0,
                stdout="status=ok value=41",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.2,
            ),
            SimpleNamespace(
                command="sleep 30 && ./bin/client status",
                exit_code=0,
                stdout="status=ok value=41",
                stderr="",
                cwd="/tmp/work",
                duration_sec=30.1,
            ),
        ],
    )

    requirement = report.requirements[0]
    assert requirement.evidence_strength == "strong"
    assert "bounded_survival_window" in requirement.evidence_strength_reasons
    assert "correct_environment_client_probe" in requirement.evidence_strength_reasons
    assert "response_or_state_validation" in requirement.evidence_strength_reasons


def test_verify_fresh_context_marks_restart_detection_as_strong_unsatisfied_evidence() -> None:
    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "service must stay up without replacement",
                        "verdict": "unsatisfied",
                        "evidence": (
                            "The service restarted: pid changed from 1201 to 1259 after 20s, showing a replacement process instead of bounded survival."
                        ),
                        "evidence_refs": ["checks_results[0]", "checks_results[1]"],
                    }
                ],
                "reason_codes": ["service_restart_detected"],
                "summary": "service was replaced",
            }
        ),
        checks_results=[
            SimpleNamespace(
                command="pgrep -f app",
                exit_code=0,
                stdout="1201",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.1,
            ),
            SimpleNamespace(
                command="sleep 20 && pgrep -f app",
                exit_code=0,
                stdout="1259",
                stderr="",
                cwd="/tmp/work",
                duration_sec=20.1,
            ),
        ],
    )

    requirement = report.requirements[0]
    assert requirement.unresolved is True
    assert requirement.evidence_strength == "strong"
    assert "crash_or_replacement_detected" in requirement.evidence_strength_reasons
    assert "bounded_survival_window" in requirement.evidence_strength_reasons


def test_verify_fresh_context_flags_uncovered_constraint_with_shape_only_evidence() -> None:
    """W5.2: a constrained task where the verifier only addresses the obvious
    "artifact exists" requirement and leaves a declared final-state/forbidden
    side-effect constraint unaddressed must surface that constraint as an
    unresolved gap, so verifier_clean cannot be true on shape-only/proxy
    evidence alone.
    """

    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "output/result.json exists",
                        "verdict": "satisfied",
                        "evidence": "workspace_diff shows result.json was written.",
                        "evidence_refs": ["workspace_diff"],
                    }
                ],
                "reason_codes": [],
                "summary": "Output artifact present.",
            }
        ),
        diff={"result.json": "sha256:abc"},
    )

    # Patch in the stated_requirements path via a direct call (the helper
    # `_verify_with_output` does not forward kwargs it doesn't know about).
    from runner.aether2.verify import verify_fresh_context as _vfc

    report = _vfc(
        task="Write output/result.json. Do not modify any files outside output/.",
        orientation={},
        diff={"result.json": "sha256:abc"},
        claim={"summary": "done"},
        checks_results=[],
        action_digest={},
        model_client=StaticModelClient(
            json.dumps(
                {
                    "requirements": [
                        {
                            "requirement": "output/result.json exists",
                            "verdict": "satisfied",
                            "evidence": "workspace_diff shows result.json was written.",
                            "evidence_refs": ["workspace_diff"],
                        }
                    ],
                    "reason_codes": [],
                    "summary": "Output artifact present.",
                }
            )
        ),
        stated_requirements=[
            "Write output/result.json.",
            "Do not modify any files outside output/.",
        ],
    )

    requirement_texts = [item.requirement for item in report.requirements]
    assert "Do not modify any files outside output/." in requirement_texts

    constraint_result = next(
        item for item in report.requirements if item.requirement == "Do not modify any files outside output/."
    )
    assert constraint_result.unresolved is True
    assert constraint_result.verdict == "unverifiable"
    assert report.has_discrepancies is True


def test_verify_fresh_context_strong_evidence_pass_resolves_clean() -> None:
    """W5.1/W5.2: a requirement satisfied by strong, decisive evidence (a
    provided check that exited cleanly, with an independent value/invariant
    comparison) must read as resolved, so verifier_clean can be True overall.
    """

    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "result is correct end to end",
                        "verdict": "satisfied",
                        "evidence": (
                            "Provided check pytest -q exited 0, compared actual output to "
                            "expected output, and parsed result.json before use."
                        ),
                        "evidence_refs": ["checks_results[0]", "workspace_diff"],
                    }
                ],
                "reason_codes": [],
                "summary": "Strong evidence: provided test suite passed and output matched expectations.",
            }
        ),
        checks_results=[
            SimpleNamespace(
                command="pytest -q",
                exit_code=0,
                stdout="2 passed",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.3,
            )
        ],
        diff={"result.json": "sha256:abc"},
    )

    requirement = report.requirements[0]
    assert requirement.evidence_strength == "strong"
    assert requirement.unresolved is False
    assert report.has_discrepancies is False


def test_verify_fresh_context_weak_self_confirming_evidence_stays_unresolved() -> None:
    """Companion direction: weak/self-confirming/proxy-only evidence must
    remain unresolved (verifier_clean stays False), so false-clean stays 0.
    """

    report = _verify_with_output(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": "tool import works without manual path edits",
                        "verdict": "satisfied",
                        "evidence": (
                            'Ran python -c "import widget" after export PYTHONPATH=/tmp/app '
                            "and command -v widget passed."
                        ),
                        "evidence_refs": ["checks_results[0]"],
                    }
                ],
                "reason_codes": [],
                "summary": "Only proxy/environment-mutated evidence available.",
            }
        ),
        checks_results=[
            SimpleNamespace(
                command='export PYTHONPATH=/tmp/app && python -c "import widget" && command -v widget',
                exit_code=0,
                stdout="widget",
                stderr="",
                cwd="/tmp/work",
                duration_sec=0.1,
            )
        ],
    )

    requirement = report.requirements[0]
    assert requirement.evidence_strength == "weak"
    assert requirement.unresolved is True
    assert report.has_discrepancies is True
