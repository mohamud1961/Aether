from pathlib import Path
from evals.performance import d3_solver_faithfulness_board as d3

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / "evals/performance/D3_SOLVER_FAITHFULNESS_BOARD_V1.json"


def test_manifest_is_exact_seven_family_board() -> None:
    m = d3.load(M)
    assert len(m["cases"]) == 7
    assert m["solver_context_mode"] == "full"
    assert m["one_attempt_per_case"] is True
    assert m["reruns_permitted"] is False


def test_provider_free_ceiling_and_known_bad_controls(tmp_path: Path) -> None:
    q = d3.qualify_provider_free(d3.load(M), tmp_path / "q")
    assert q["status"] == "PASS"
    assert q["provider_calls"] == 0
    assert q["case_count"] == 7
    assert all(r["ceiling_pass"] and r["known_bad_rejected"] for r in q["rows"])


def _rows(passed: bool = True):
    m = d3.load(M)
    return [
        {"case_id": c["id"], "family": c["family"], "run_status": "completed", "provider_invalid": False,
         "passed": passed, "solver_provider_attempts": 1, "verifier_provider_attempts": 1}
        for c in m["cases"]
    ]


def test_adjudication_requires_all_seven_pass() -> None:
    m = d3.load(M)
    assert d3.adjudicate(_rows(), m)["decision"] == "PASS"
    rows = _rows(); rows[3]["passed"] = False
    assert d3.adjudicate(rows, m)["decision"] == "FAIL"


def test_provider_invalid_stops_inconclusive() -> None:
    m = d3.load(M)
    rows = _rows()[:3]; rows[-1]["run_status"] = "timeout"; rows[-1]["provider_invalid"] = True
    out = d3.adjudicate(rows, m)
    assert out["decision"] == "INCONCLUSIVE_PROVIDER_FAILURE"
    assert out["attempted_case_count"] == 3


def test_false_finding_and_unavailable_reviewers_are_deterministic() -> None:
    false = d3.FalseFindingVerifier()
    first = false([], max_output_tokens=100)
    assert '"kind": "inspect"' in first
    second = false([{"content": "inspection:1:1:inspect-0"}], max_output_tokens=100)
    assert 'needs_repair' in second and 'negative' in second
    unavailable = d3.UnavailableVerifier()
    try:
        unavailable([], max_output_tokens=100)
    except RuntimeError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("unavailable reviewer must fail deterministically")
