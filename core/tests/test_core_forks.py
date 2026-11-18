"""AETHER_CORE_RIVAL=forks: a fresh reader names read-only observations of the machine; Core runs them once on a
read-only clone before any work, and the worker's first request carries only what the machine showed."""

from __future__ import annotations

import dataclasses
import json

from aether.core import forks
from aether.core.harbor_agent import build_config
from tests.core_fakes import call
from tests.test_core_attack import _config, _text
from tests.test_core_start_copy import BASE
from tests.test_core_v2 import _run


def _forks_config(tmp_path):
    config, made = _config(tmp_path)
    return dataclasses.replace(config, card_challenge="forks"), made


def test_forks_mode_sets_its_flags():
    c = build_config(environ={**BASE, "AETHER_CORE_RIVAL": "forks"})
    assert c.card is True and c.card_challenge == "forks" and c.rival is False


def test_probe_blocks_parse_and_clip():
    out = "noise\nPROBE tools\nran: which sshd\nsaw: not found\nPROBE big\nran: x\nsaw: " + "y" * 2000 + "\n"
    found = forks.blocks(out)
    assert [b["name"] for b in found] == ["tools", "big"] and "saw: not found" in found[0]["body"]
    assert found[1]["body"].endswith("[...]") and len(found[1]["body"]) < 1000


def test_observations_reach_the_first_request_without_the_readers_forks(tmp_path):
    (tmp_path / "work").mkdir(exist_ok=True)
    probe = 'echo "PROBE sshd"; echo "ran: command -v sshd"; echo "saw: absent"; touch probe_wrote_here'
    reader = f"Part 2 FORK_TEXT literal or placeholder?\n```sh\n{probe}\n```\nPROBE sshd -> MAPPING_TEXT"
    script = [call("finish", {"summary": "done"}, "c0")]
    config, made = _forks_config(tmp_path)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(reader)])
    assert result.status == "finished" and made == [{"egress": True}]
    row = [r for r in rows if r["event"] == "forks"][-1]
    assert row["shown"] is True and row["probes"] == 1
    first = json.dumps(next(r for r in client.requests if "tools" in r)["messages"])
    assert "machine_observations" in first and "saw: absent" in first
    assert "FORK_TEXT" not in first and "MAPPING_TEXT" not in first and "Part 2" not in first
    assert not (tmp_path / "work" / "probe_wrote_here").exists()  # the probes ran on the clone only
    assert len([r for r in client.requests if "tools" in r]) == 1  # the finish took effect: nothing handed back


def test_no_script_means_no_note(tmp_path):
    script = [call("finish", {"summary": "done"}, "c0")]
    config, _ = _forks_config(tmp_path)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text("only prose")])
    row = [r for r in rows if r["event"] == "forks"][-1]
    assert row["shown"] is False and row["script"] is False
    assert "machine_observations" not in json.dumps(client.requests[-1]["messages"])


def test_without_a_host_clone_factory_nothing_runs(tmp_path):
    script = [call("finish", {"summary": "done"}, "c0")]
    config, _ = _forks_config(tmp_path)
    config = dataclasses.replace(config, make_clone=None)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text("```sh\necho hi\n```")])
    row = [r for r in rows if r["event"] == "forks"][-1]
    assert row["shown"] is False and row["error"] == "no host clone factory"
