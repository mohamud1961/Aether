"""AETHER_CORE_RIVAL=attack: a fresh reader's attack checks, run on a clone at the finish; only result blocks return."""

from __future__ import annotations

import dataclasses
import json
import shutil
import uuid

from aether.core import attack
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv, call, chunk
from tests.test_core_start_copy import BASE
from tests.test_core_v2 import _clm_config, _run


def _text(content: str) -> list:
    return [chunk(content=content), chunk(finish="stop")]


class _Clone(LocalEnv):
    """A copy of tmp_path standing in for a container clone (same absolute paths, separate files)."""

    def __init__(self, original):
        copy = original.parent / f"clone-{uuid.uuid4().hex[:6]}"
        shutil.copytree(original, copy, symlinks=True)
        super().__init__(copy)
        self.original = str(original)

    def _map(self, text):
        return None if text is None else str(text).replace(self.original, str(self.root))

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        return await super().exec(self._map(command), cwd=self._map(cwd), env=env, timeout_sec=timeout_sec)

    async def upload_file(self, source_path, target_path):
        await super().upload_file(source_path, self._map(target_path))

    async def close(self):
        pass


def _config(tmp_path):
    made = []

    async def clone(env, timeout_s=None, read_only=False, **egress):
        made.append(egress)
        return _Clone(tmp_path)

    return dataclasses.replace(_clm_config(tmp_path), card=True, card_challenge="attack", make_clone=clone), made


def _check(name, cmd, expected, result):
    return f'echo "CHECK {name}"; echo "ran: {cmd}"; echo "expected: {expected}"; echo "got: $({cmd})"; echo "result: {result}"'


def test_attack_mode_sets_its_flags():
    c = build_config(environ={**BASE, "AETHER_CORE_RIVAL": "attack"})
    assert c.card is True and c.card_challenge == "attack" and c.card_probe is False and c.rival is False


def test_result_blocks_parse_and_never_carry_other_output():
    out = "noise CONCERN\nCHECK port\nran: curl x\nexpected: 200\ngot: 000\nresult: FAIL\nmore noise\n"
    found = attack.blocks(out)
    assert found == [{"name": "port", "body": "ran: curl x\nexpected: 200\ngot: 000", "result": "FAIL"}]
    assert "noise" not in attack.render(found) and "CONCERN" not in attack.render(found)


def test_a_failing_check_returns_only_result_blocks_and_runs_on_a_clone(tmp_path):
    out = tmp_path / "work" / "out.txt"
    script = [
        call("write_file", {"path": str(out), "content": "41\n"}, "c0"),
        call("finish", {"summary": "answer written"}, "c1"),
        call("terminal", {"input": "echo fixed"}, "c2"),
        call("finish", {"summary": "checked"}, "c3"),
        call("finish", {"summary": "done"}, "c4"),
    ]
    checks = "\n".join(["echo tampered > out.txt.attack", _check("value", f"cat {out}", "42", "FAIL")])
    reader = f"Part 1 CONCERN_TEXT the value may be off by one.\n```sh\n{checks}\n```\n"
    config, made = _config(tmp_path)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(reader)])
    assert result.status == "finished"
    row = [r for r in rows if r["event"] == "rival"][-1]
    assert row["mode"] == "attack" and row["FAIL"] == 1 and row["rounds"] == 2 and made[0] == {"egress": True}
    reader_request = json.dumps(next(r for r in client.requests if "tools" not in r)["messages"])
    assert "MACHINE FACTS" in reader_request and "answer written" not in reader_request and "41" not in reader_request
    handback = json.dumps(client.requests[-2]["messages"][-1])
    assert "<check_results>" in handback and "result: FAIL" in handback and "expected: 42" in handback
    assert "CONCERN_TEXT" not in handback and "Part 1" not in handback
    assert not (tmp_path / "work" / "out.txt.attack").exists()  # the script ran on the clone only


def test_all_checks_passing_lets_the_first_finish_end_the_run(tmp_path):
    out = tmp_path / "work" / "out.txt"
    script = [call("write_file", {"path": str(out), "content": "42\n"}, "c0"), call("finish", {"summary": "done"}, "c1")]
    reader = f"```sh\n{_check('value', f'cat {out}', '42', 'PASS')}\n```"
    config, _ = _config(tmp_path)
    result, rows, _ = _run(tmp_path, script, config=config, text_script=[_text(reader)])
    row = [r for r in rows if r["event"] == "rival"][-1]
    assert result.status == "finished" and row["PASS"] == 1 and row["FAIL"] == 0 and row["again"] is False


def test_an_untested_script_is_repaired_once_by_the_reader_and_the_repair_is_used(tmp_path):
    out = tmp_path / "work" / "out.txt"
    script = [
        call("write_file", {"path": str(out), "content": "41\n"}, "c0"),
        call("finish", {"summary": "done"}, "c1"),
        call("finish", {"summary": "done again"}, "c2"),
        call("finish", {"summary": "done thrice"}, "c3"),
    ]
    first = "```sh\n" + _check("value", "nosuchtool", "42", "UNTESTED") + "\n```"
    fixed = "```sh\n" + _check("value", f"cat {out}", "42", "FAIL") + "\n```"
    config, _ = _config(tmp_path)
    result, rows, client = _run(tmp_path, script, config=config, text_script=[_text(first), _text(fixed)])
    row = [r for r in rows if r["event"] == "rival"][0]
    assert row["repaired"] is True and "UNTESTED" in row["repair"] and row["FAIL"] == 1
    repair_request = json.dumps([r for r in client.requests if "tools" not in r][1]["messages"])
    assert "Rewrite the whole script" in repair_request and "done" not in repair_request.split("Rewrite")[0][-200:]


def test_no_script_means_the_finish_takes_effect(tmp_path):
    config, _ = _config(tmp_path)
    result, rows, _ = _run(tmp_path, [call("finish", {"summary": "done"}, "c0")], config=config,
                           text_script=[_text("only prose")])
    row = [r for r in rows if r["event"] == "rival"][-1]
    assert result.status == "finished" and row["script"] is False


def test_without_a_host_clone_factory_no_check_runs_and_the_finish_takes_effect(tmp_path):
    config = dataclasses.replace(_clm_config(tmp_path), card=True, card_challenge="attack")
    reader = "```sh\necho touched > out.txt.attack\n```"
    result, rows, _ = _run(tmp_path, [call("finish", {"summary": "done"}, "c0")], config=config,
                           text_script=[_text(reader)])
    row = [r for r in rows if r["event"] == "rival"][-1]
    assert result.status == "finished" and "no host clone factory" in row["error"]
    assert not (tmp_path / "work" / "out.txt.attack").exists()
