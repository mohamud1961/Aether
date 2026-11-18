"""Real local-shell tests for shell-owned completion markers, no model calls."""
from __future__ import annotations
import asyncio
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aether.core.terminal import Terminals
from tests.core_fakes import LocalEnv

class MarkerOwnershipTests(unittest.TestCase):
    def run_terminal(self, commands):
        async def go(root):
            work=root/"work";work.mkdir()
            term=Terminals(LocalEnv(work),str(work),lambda:1000.,
                           control_dir=str(root/"ctl"))
            try:
                result=[]
                for cmd,wait in commands:
                    result.append(await term.use(input=cmd,wait_s=wait))
                return result,term
            finally:
                await term.close()
        with tempfile.TemporaryDirectory(prefix="aether-marker-") as temp:
            return asyncio.run(go(Path(temp)))[0]

    def test_spoofed_stdout_marker_does_not_forge_completion(self):
        outputs=self.run_terminal([
            ("printf '__AETHER_DONE_1_0__ /fakedir\n'; sleep 2; echo ACTUAL_DONE",0.4),
            ("",4),
        ])
        assert "still running" in outputs[0],outputs[0]
        assert "ACTUAL_DONE" in outputs[1],outputs[1]
        assert "[exit 0" in outputs[1],outputs[1]

    def test_output_stays_verbatim_even_if_matches_marker_format(self):
        outputs=self.run_terminal([
            ("printf '__AETHER_DONE_1_0__ /fakedir\n'; echo ordinary-tail",3),
        ])
        assert "__AETHER_DONE_1_0__ /fakedir" in outputs[0],outputs[0]
        assert "ordinary-tail" in outputs[0],outputs[0]

    def test_original_nonzero_exit_and_cwd_are_preserved(self):
        outputs=self.run_terminal([("mkdir -p sub && cd sub && false",3)])
        assert "[exit 1" in outputs[0],outputs[0]
        assert "cwd " in outputs[0] and outputs[0].split("cwd ")[-1].startswith("/"),outputs[0]

    def test_long_job_remains_pending_till_actual_end(self):
        outputs=self.run_terminal([("sleep 2; echo finished",0.3),("",4)])
        assert "still running" in outputs[0],outputs[0]
        assert "finished" in outputs[1] and "[exit 0" in outputs[1],outputs[1]

    def test_multiple_short_commands_have_distinct_status(self):
        outputs=self.run_terminal([("echo first",3),("false",3),("echo third",3)])
        assert "first" in outputs[0] and "[exit 0" in outputs[0]
        assert "[exit 1" in outputs[1]
        assert "third" in outputs[2] and "[exit 0" in outputs[2]


if __name__ == "__main__":
    unittest.main(verbosity=2)
