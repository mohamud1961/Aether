"""Terminal ownership and protocol edge cases against actual local shell.

No model, network or task grader. Mac pipe fallback; Linux PTY is separate.
"""
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

class TerminalExtended(unittest.TestCase):
    def run_session(self,steps):
        async def run(root):
            work=root/"task";work.mkdir()
            term=Terminals(LocalEnv(work),str(work),lambda:300.,control_dir=str(root/"control"))
            output=[]
            try:
                for params in steps:
                    output.append(await term.use(**params))
            finally:
                await term.close()
            return output
        with tempfile.TemporaryDirectory(prefix="aether-terminal-ext-") as root:
            return asyncio.run(run(Path(root)))

    def test_separate_terminals_have_separate_cwd(self):
        outs=self.run_session([
            {"name":"main","input":"mkdir -p dir-a && cd dir-a && pwd","wait_s":2},
            {"name":"other","input":"pwd","wait_s":2},
            {"name":"main","input":"pwd","wait_s":2},
        ])
        self.assertIn("/dir-a",outs[0])
        self.assertNotIn("/dir-a",outs[1])
        self.assertIn("/dir-a",outs[2])

    def test_exit_nonzero_then_success_separate_receipts(self):
        outs=self.run_session([
            {"input":"false","wait_s":2},
            {"input":"echo recovered","wait_s":2},
        ])
        self.assertIn("[exit 1",outs[0])
        self.assertIn("[exit 0",outs[1])
        self.assertIn("recovered",outs[1])

    def test_pipeline_stage_failure_is_visible_if_supported(self):
        outs=self.run_session([{"input":"false | true","wait_s":2}])
        # Exit status belongs to final stage; no semantic task grade can be
        # inferred from it. Shell may also report component statuses.
        self.assertIn("[exit 0",outs[0])
        self.assertIn("cwd ",outs[0])

    def test_shell_exit_not_misreported_as_success(self):
        outs=self.run_session([{"input":"exit 7","wait_s":2},
                               {"input":"","wait_s":0},
                               {"input":"echo new-shell","wait_s":2}])
        self.assertNotIn("[exit 0",outs[0])
        self.assertIn("terminal main exited",outs[0])
        self.assertIn("new-shell",outs[2])

    def test_no_output_command_eventually_completes(self):
        outs=self.run_session([{"input":"sleep 1","wait_s":0.1},
                               {"input":"","wait_s":3}])
        self.assertIn("still running",outs[0])
        self.assertIn("[exit 0",outs[1])

    def test_program_can_print_marker_without_consume_or_completion(self):
        outs=self.run_session([{"input":"printf '__AETHER_DONE_1_0__ /evil\\n'; sleep 1; printf real-end","wait_s":.1},
                               {"input":"","wait_s":3}])
        self.assertIn("still running",outs[0])
        self.assertIn("__AETHER_DONE_1_0__ /evil",outs[0])
        self.assertIn("real-end",outs[1])
        self.assertIn("[exit 0",outs[1])

    def test_unsubmitted_interrupt_command_does_not_leak_into_next(self):
        outs=self.run_session([
            {"input":"sleep 4; echo OLD_COMPLETE","wait_s":.1},
            {"input":"echo FORBIDDEN_TEXT","interrupt":True,"wait_s":2},
            {"input":"echo permitted","name":"other","wait_s":2},
        ])
        self.assertIn("supplied input was not submitted",outs[1])
        self.assertNotIn("FORBIDDEN_TEXT",outs[1])
        self.assertIn("permitted",outs[2])

    def test_invalid_terminal_name_is_rejected(self):
        async def run(root):
            work=root/"task";work.mkdir()
            term=Terminals(LocalEnv(work),str(work),lambda:20.,control_dir=str(root/"ctl"))
            try:
                with self.assertRaises(ValueError):
                    await term.use(name="../evil",input="echo forbidden")
                with self.assertRaises(ValueError):
                    await term.use(name="",input="echo forbidden")
                with self.assertRaises(ValueError):
                    await term.use(name="x"*33,input="echo forbidden")
            finally:
                await term.close()
        with tempfile.TemporaryDirectory(prefix="aether-bad-name-") as root:
            asyncio.run(run(Path(root)))


if __name__=="__main__":
    unittest.main(verbosity=2)
