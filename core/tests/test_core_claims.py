"""Unbacked-claim flags in the finish report: one-directional, mechanical, no model call."""

import asyncio

from aether.core import claims
from aether.core.finish_report import StepRecord, record
from tests.core_fakes import LocalEnv


def _step(n, tool, text, out="", wrote=""):
    return StepRecord(n, tool, text, 0 if tool == "terminal" else None, False, wrote, claims.numbers(out))


def test_numbers_normalise_and_skip_paths_and_versions():
    assert claims.numbers("1,234 rows; 1.50 s; 17.") == {"1234", "1.5", "17"}
    assert claims.numbers("built vectorops-0.1.0.tar.gz version 0.1.0 at /app/out_3.txt") == frozenset()


def test_a_count_no_output_contains_is_flagged_and_one_that_is_shown_is_not():
    # financial-document case: categories 10 + 10 seen, total 17 never produced by any step
    steps = [_step(1, "terminal", "ls invoices | wc -l; ls other | wc -l", out="10\n10\n")]
    summary = "All 17 documents processed: 10 invoices, 10 other."
    assert claims.ungrounded_numbers(summary, steps, task="Sort the documents.") == ["17"]
    # a number from the task text is grounded (port 8080)
    assert claims.ungrounded_numbers("Server up on port 8080.", [], task="serve on port 8080") == []


def test_verification_of_a_file_no_step_touched_after_its_write_is_flagged(tmp_path):
    work = str(tmp_path)
    files = [
        {"path": f"{work}/a.csv", "last_file_tool_write": 1},
        {"path": f"{work}/b.txt", "last_file_tool_write": 2},
    ]
    steps = [
        _step(1, "write_file", "a.csv", wrote=f"{work}/a.csv"),
        _step(2, "write_file", "b.txt", wrote=f"{work}/b.txt"),
        _step(3, "terminal", "python3 check.py a.csv"),
    ]
    unsupported, unscoped, _ = claims.verification_claims(
        "Verified a.csv against the spec. Checked b.txt too. All tests pass.", files, steps, work
    )
    assert unsupported == [{"claim": "Checked b.txt too.", "no_step_identified_on": ["b.txt"]}]
    assert unscoped == ["All tests pass."]


def test_verification_against_an_input_nothing_read_is_flagged(tmp_path):
    steps = [_step(1, "terminal", "sed -i s/a/b/ out.txt")]
    unsupported, _, _ = claims.verification_claims("Verified against synonyms.txt.", [], steps, str(tmp_path))
    assert unsupported[0]["no_step_identified_on"] == ["synonyms.txt"]
    steps.append(_step(2, "read_file", "synonyms.txt"))
    assert claims.verification_claims("Verified against synonyms.txt.", [], steps, str(tmp_path))[0] == []


def test_named_files_missing_at_the_end(tmp_path):
    (tmp_path / "out.txt").write_text("x\n")
    env = LocalEnv(tmp_path)
    missing = asyncio.run(claims.missing_files(env, "Wrote out.txt and /app/result.json.", str(tmp_path)))
    assert missing == ["/app/result.json"]


def test_a_truthful_summary_gets_no_flags(tmp_path):
    (tmp_path / "out.txt").write_text("42\n")
    files = [{"path": f"{tmp_path}/out.txt", "last_file_tool_write": None}]
    steps = [_step(1, "terminal", "python3 solve.py > out.txt; cat out.txt", out="42\n")]
    found = asyncio.run(
        claims.check(LocalEnv(tmp_path), "Wrote 42 to out.txt and checked out.txt.", files, steps, str(tmp_path), "")
    )
    assert found == {
        "meaning": "no supporting observation identified in the captured record (not: did not happen)",
        "verification_no_step_identified": [],
        "verification_possibly_covered_by_test_run": [],
        "verification_unscoped": [],
        "numbers_not_found_verbatim": [],
        "named_files_not_found": [],
    }


def test_a_hidden_pipeline_failure_is_recorded_from_the_terminal_status():
    out = "Traceback ...\n[exit 0 · last pipeline's stage exits 1 | 0 · 0.2s · terminal main · cwd /app]"
    rec = record(4, "terminal", {"input": "python3 run.py | tail"}, out, "/app")
    assert rec.exit == 0 and rec.stage_failed
    assert not record(5, "terminal", {"input": "true"}, "[exit 0 · 0.1s · terminal main · cwd /app]", "/app").stage_failed


# ----- false-positive and staleness cases (review of 2026-10-21) -----------------------------------------------------
def test_a_test_run_after_the_last_write_is_possible_coverage_not_a_flag(tmp_path):
    # pytest reads out.csv through the code under test without the command naming it
    work = str(tmp_path)
    files = [{"path": f"{work}/out.csv", "last_file_tool_write": 1}]
    steps = [_step(1, "write_file", "out.csv", wrote=f"{work}/out.csv"), _step(2, "terminal", "pytest -q tests/")]
    unsupported, _, covered = claims.verification_claims("Verified out.csv.", files, steps, work)
    assert unsupported == [] and covered == [
        {"claim": "Verified out.csv.", "possibly_covered_by": [{"file": "out.csv", "test_run_steps": [2]}]}
    ]


def test_a_test_run_before_the_last_write_does_not_cover_it(tmp_path):
    work = str(tmp_path)
    files = [{"path": f"{work}/out.csv", "last_file_tool_write": 2}]
    steps = [_step(1, "terminal", "pytest -q"), _step(2, "write_file", "out.csv", wrote=f"{work}/out.csv")]
    unsupported, _, covered = claims.verification_claims("Verified out.csv.", files, steps, work)
    assert covered == [] and unsupported[0]["no_step_identified_on"] == ["out.csv"]


def test_a_check_before_the_last_write_is_stale_and_does_not_count(tmp_path):
    # the file was read, then rewritten; the read checked a former version
    work = str(tmp_path)
    files = [{"path": f"{work}/a.csv", "last_file_tool_write": 3}]
    steps = [
        _step(1, "write_file", "a.csv", wrote=f"{work}/a.csv"),
        _step(2, "read_file", "a.csv"),
        _step(3, "write_file", "a.csv", wrote=f"{work}/a.csv"),
    ]
    unsupported, _, _ = claims.verification_claims("Checked a.csv.", files, steps, work)
    assert unsupported[0]["no_step_identified_on"] == ["a.csv"]


def test_a_path_alias_matches_by_name(tmp_path):
    work = str(tmp_path)
    files = [{"path": f"{work}/results.csv", "last_file_tool_write": 1}]
    steps = [_step(1, "write_file", "results.csv", wrote=f"{work}/results.csv"), _step(2, "terminal", "head ./results.csv")]
    assert claims.verification_claims("Verified ./results.csv.", files, steps, work)[0] == []


def test_a_calculated_number_is_reported_as_not_found_verbatim_not_as_false(tmp_path):
    # 20 = 10 + 10 is a legitimate calculation; the flag only says the number was not seen verbatim
    steps = [_step(1, "terminal", "wc -l a b", out="10 a\n10 b\n")]
    assert claims.ungrounded_numbers("20 rows in total.", steps, task="") == ["20"]
    found = asyncio.run(claims.check(LocalEnv(tmp_path), "20 rows in total.", [], steps, str(tmp_path), ""))
    assert "not: did not happen" in found["meaning"]


def test_a_symlinked_file_is_found(tmp_path):
    (tmp_path / "real.txt").write_text("x\n")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    assert asyncio.run(claims.missing_files(LocalEnv(tmp_path), "Wrote link.txt.", str(tmp_path))) == []
