from runner.aether2.prompts import (
    COMPLETION_REMINDER_INTRO,
    DOCTRINE_LINES,
    STRATEGY_RESET_REMINDER,
    SYSTEM_PROMPT,
    TASK_DONE_REMINDER,
)


def test_prompt_exports_doctrine_lines_verbatim() -> None:
    assert len(DOCTRINE_LINES) == 2
    assert (
        "Missing tools can usually be installed (apt/pip/npm); prefer installing or bootstrapping over abandoning."
        in DOCTRINE_LINES
    )
    assert (
        "Plans are model-owned and model-updatable. State a brief plan when the work is multi-step, and revise it when evidence changes the approach."
        in DOCTRINE_LINES
    )
    for line in DOCTRINE_LINES:
        assert line in SYSTEM_PROMPT


def test_system_prompt_contains_aether2_role_boundaries() -> None:
    assert "The model pilots." in SYSTEM_PROMPT
    assert "The harness instruments." in SYSTEM_PROMPT
    assert "The verifier reflects." in SYSTEM_PROMPT
    assert "The ledger remembers." in SYSTEM_PROMPT
    assert "The grader decides." in SYSTEM_PROMPT
    assert "Choose the strategy yourself" in SYSTEM_PROMPT
    assert "Inspect first." in SYSTEM_PROMPT
    assert "Verify the real outcome." in SYSTEM_PROMPT
    assert "externally observable behavior" in SYSTEM_PROMPT
    assert "Do not read hidden tests or hidden grader files." in SYSTEM_PROMPT
    assert COMPLETION_REMINDER_INTRO in SYSTEM_PROMPT
    assert STRATEGY_RESET_REMINDER in SYSTEM_PROMPT
    assert TASK_DONE_REMINDER in SYSTEM_PROMPT


def test_system_prompt_contains_final_completion_and_evidence_rules() -> None:
    assert "Tool observations are the only truth." in SYSTEM_PROMPT
    assert "Never invent command output" in SYSTEM_PROMPT
    assert "Do not repeat a failed command or strategy without a changed hypothesis." in SYSTEM_PROMPT
    assert "A successful command that does not advance a requirement is not real progress." in SYSTEM_PROMPT
    assert "task_done is a completion claim that triggers verification" in SYSTEM_PROMPT
    assert "it is not proof by itself" in SYSTEM_PROMPT
    assert "known requirement remains unresolved" in SYSTEM_PROMPT
    assert "bounded survival evidence" in SYSTEM_PROMPT
    assert "A process existing, a port being open, or one startup probe is weak evidence by itself." in SYSTEM_PROMPT
    assert "Do not expose secrets" in SYSTEM_PROMPT


def test_prompt_is_generic_and_avoids_benchmark_vocabulary() -> None:
    prompt_text = "\n".join([SYSTEM_PROMPT, *DOCTRINE_LINES]).lower()
    banned_terms = [
        "terminal-bench",
        "terminalbench",
        "harbor",
        "tb2",
        "tb2.0",
        "extract-moves-from-video",
        "install-windows-3.11",
        "difficulty",
        "category",
        "tags",
        "search_receipts",
        "view_receipt",
        "view_file_cache",
        "search_files",
        "probe_service",
    ]

    for term in banned_terms:
        assert term not in prompt_text
