"""AETHER_CORE_SHELL_KIT (shellkit): apply_patch, view_image, job, pyk and ctx as terminal commands.

Each test runs the real loop with a real shell (LocalEnv) and checks the state the command left, with a known-bad
run that has the switch off.
"""

import json
import os

import pytest

from aether.core import images
from aether.core.clm import ClmSettings
from aether.core.harbor_config import build_config
from aether.core.loop import CoreConfig
from aether.core.shellkit import scripts
from tests.core_fakes import call
from tests.test_core_image_region import _wide
from tests.test_core_v2 import _run

PATCH = "apply_patch <<'EOF'\n*** Begin Patch\n*** Update File: m.py\n@@\n-alpha = 1\n+alpha = 10\n*** End Patch\nEOF\n"


@pytest.fixture(autouse=True)
def _kit_root(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts, "ROOT", str(tmp_path / "kit"))
    monkeypatch.delenv("AETHER_CORE_REPL_PYTHON", raising=False)


def _term(cmd, cid, wait=30):
    return call("terminal", {"input": cmd, "wait_s": wait}, cid)


def _go(tmp_path, cmds, kit=True, **cfg):
    (tmp_path / "work").mkdir(exist_ok=True)
    script = [_term(c, f"t{i}") for i, c in enumerate(cmds)] + [call("finish", {"summary": "done"}, "f")]
    result, rows, client = _run(tmp_path, script, config=CoreConfig(shell_kit=kit, control_dir=str(tmp_path / "ctl"),
                                                                    **cfg))
    assert result.status == "finished", result.error
    outs = [r["result"] for r in rows if r["event"] == "tool" and r["name"] == "terminal"]
    return outs, rows, client


def test_apply_patch_runs_inside_a_command_chain(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "m.py").write_text("alpha = 1\nbeta = 2\n")
    outs, _, client = _go(tmp_path, [PATCH + "python3 -c 'import m; print(m.alpha * 2)'"])
    assert "Success" in outs[0] and "20" in outs[0]  # the next command in the chain saw the patched file
    assert (tmp_path / "work" / "m.py").read_text() == "alpha = 10\nbeta = 2\n"
    spec = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "terminal")
    assert "apply_patch" in spec["function"]["description"] and "ctx" not in spec["function"]["description"]


def test_known_bad_without_the_kit_there_is_no_apply_patch_command(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "m.py").write_text("alpha = 1\nbeta = 2\n")
    outs, _, client = _go(tmp_path, [PATCH], kit=False)
    assert "not found" in outs[0]
    assert (tmp_path / "work" / "m.py").read_text() == "alpha = 1\nbeta = 2\n"
    spec = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "terminal")
    assert "apply_patch" not in spec["function"]["description"]


def test_a_patch_with_one_missing_hunk_writes_no_file(tmp_path):
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "a.py").write_text("one\n")
    (tmp_path / "work" / "b.py").write_text("two\n")
    patch = ("apply_patch <<'EOF'\n*** Begin Patch\n*** Update File: a.py\n-one\n+ONE\n*** Update File: b.py\n"
             "-three\n+THREE\n*** End Patch\nEOF\necho status=$?")
    outs, _, _ = _go(tmp_path, [patch])
    assert "nothing was written" in outs[0] and "status=1" in outs[0]
    assert (tmp_path / "work" / "a.py").read_text() == "one\n" and (tmp_path / "work" / "b.py").read_text() == "two\n"


def test_a_job_runs_in_the_background_and_its_end_is_reported_once(tmp_path):
    outs, rows, _ = _go(tmp_path, ["job start build 'sleep 1; echo built-ok'", "sleep 2", "true", "job log build",
                                   "job start long 'sleep 60' && job kill long", "true"])
    assert "started" in outs[0] and "ended" not in outs[0]
    notices = [o for o in outs if "[job build ended: exit 0" in o]
    assert len(notices) == 1 and outs.index(notices[0]) in (1, 2)
    assert "built-ok" in outs[3]
    assert "job long: exit killed" in outs[4] and not any("long ended" in o for o in outs)  # its own kill: no notice


def test_known_bad_without_the_kit_no_job_and_no_notice(tmp_path):
    outs, _, _ = _go(tmp_path, ["job start build 'sleep 1; echo built-ok'", "sleep 2", "true"], kit=False)
    assert "not found" in outs[0] and not any("ended" in o for o in outs)


def test_pyk_keeps_variables_between_terminal_calls(tmp_path):
    outs, _, _ = _go(tmp_path, ["pyk 'data = [n * n for n in range(10)]' && echo loaded",
                                "pyk 'sum(data) + 1'", "pyk --reset"])
    assert "loaded" in outs[0] and "286" in outs[1]


def test_view_image_in_a_chain_shows_the_image_after_the_command(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "a.png")
    outs, _, client = _go(tmp_path, ["view_image a.png && echo after"], images=True)
    assert "after" in outs[0] and "shown below" in outs[0]
    final = client.requests[-1]["messages"]
    assert sum(images.count(m) for m in final) == 1


def _clm(tmp_path):
    settings = ClmSettings(budget_tokens=200_000, reserve_tokens=500, mirror_path=str(tmp_path / "ctl" / "live"),
                           history_path=str(tmp_path / "ctl" / "history"))
    return {"context": "clm", "clm": settings}


BIG = "printf 'Q%.0s' $(seq 1 30000); echo"
PICK = "$(ctx list | awk '$3 + 0 > 5000 && !n {print $1; n = 1}')"


def _has_big(request):
    return any("Q" * 1000 in json.dumps(m) for m in request["messages"])


def test_ctx_drop_removes_the_whole_turn_from_the_next_request(tmp_path):
    outs, rows, client = _go(tmp_path, [BIG, "ctx list", f"ctx drop {PICK}", "echo next"], **_clm(tmp_path))
    assert "total" in outs[1] and "tool" in outs[1]
    assert "[ctx: dropped turns" in outs[2]
    assert _has_big(client.requests[2]) and not _has_big(client.requests[-1])
    edits = [r for r in rows if r["event"] == "context_edit"]
    assert edits and edits[-1]["accepted"]


def test_ctx_stub_keeps_the_output_in_a_file(tmp_path):
    outs, _, client = _go(tmp_path, [BIG, f"ctx stub {PICK}", "echo next"], **_clm(tmp_path))
    assert "[ctx: stubbed turns" in outs[1]
    assert not _has_big(client.requests[-1])
    assert any("saved in" in json.dumps(m) for m in client.requests[-1]["messages"])
    saved = [p for p in os.listdir(tmp_path / "kit" / "ctx")]
    assert saved and "Q" * 1000 in (tmp_path / "kit" / "ctx" / saved[0]).read_text()


def test_known_bad_without_the_kit_the_output_stays(tmp_path):
    outs, _, client = _go(tmp_path, [BIG, f"ctx drop {PICK}", "echo next"], kit=False, **_clm(tmp_path))
    assert "not found" in outs[1] and _has_big(client.requests[-1])


def test_switch_is_opt_in_and_validated():
    env = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
           "AETHER_CORE_IMAGES": "off"}
    assert not build_config(environ=env).shell_kit
    assert build_config(environ={**env, "AETHER_CORE_SHELL_KIT": "on"}).shell_kit


def test_drop_takes_a_call_with_all_its_results_and_reports_bad_turns():
    from aether.core import shellkit

    text = ("[[CTX_TURN 0 role=user]]\ntask\n[[CTX_TURN 1 role=assistant]]\nrun\n[[CTX_TURN 2 role=tool]]\na\n"
            "[[CTX_TURN 3 role=tool]]\nb\n[[CTX_TURN 4 role=assistant]]\nnext\n")
    new, report = shellkit.edit(text, [("drop", "3"), ("stub", "4"), ("drop", "7")])
    assert new == "[[CTX_TURN 0 role=user]]\ntask\n[[CTX_TURN 4 role=assistant]]\nnext\n"
    assert "dropped turns 1-3" in report and "turn 4 is your own turn" in report and "turn 7 is not" in report
