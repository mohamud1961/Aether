"""Falsifiers for Record.snapshot task-named file coverage.

The baseline mtime-only recorder misses existing deliverables with a preserved
old mtime. The test requires this failure to be visible, but captures remain
bounded selected-file evidence, not whole-workspace or task correctness.
"""
import asyncio
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aether.core.record import Record
from aether.core.receipt import MARKER
from tests.core_fakes import LocalEnv


class NamedCoverage(unittest.TestCase):
    def fixture(self,callback):
        async def go(root):
            app=root/"app";app.mkdir()
            control=root/"control";control.mkdir()
            (control/MARKER).write_text("marker")
            def instance(task):
                return Record(LocalEnv(app),str(app),str(control),
                              remaining=lambda:300.,trace=lambda *_a,**_k:None,
                              measure=False,task=task)
            return await callback(root,app,control,instance)
        with tempfile.TemporaryDirectory(prefix="aether-record-named-") as root:
            return asyncio.run(go(Path(root)))

    def test_preserved_old_mtime_named_file_is_captured_and_saved(self):
        async def check(root,app,ctl,instance):
            path=app/"out.txt";path.write_text("PRESERVED_OUTPUT")
            os.utime(path,(1234,1234))
            record=instance(f"Create {path}")
            snap=await record.snapshot(save=True)
            expected=hashlib.sha256(b"PRESERVED_OUTPUT").hexdigest()
            self.assertEqual(snap.get("out.txt"),expected)
            self.assertEqual((ctl/"versions"/expected/"out.txt").read_bytes(),b"PRESERVED_OUTPUT")
        self.fixture(check)

    def test_named_candidate_prioritized_before_300_ordinary_changed_files(self):
        async def check(root,app,ctl,instance):
            folder=app/"many";folder.mkdir()
            for i in range(340):
                (folder/f"file-{i}.txt").write_text(f"junk{i}")
            output=app/"answer.txt";output.write_text("gold")
            os.utime(output,(1234,1234))
            record=instance(f"Make {output}")
            snap=await record.snapshot(save=False)
            self.assertIn("answer.txt",snap)
            self.assertLessEqual(len(snap),300)
        self.fixture(check)

    def test_symlink_parent_must_not_capture_external_file(self):
        async def check(root,app,ctl,instance):
            outside=root/"private";outside.mkdir()
            target=outside/"answer.txt";target.write_text("OUTSIDE")
            os.symlink(outside,app/"link",target_is_directory=True)
            record=instance(f"Create {app/'link'/'answer.txt'}")
            snap=await record.snapshot(save=False)
            self.assertNotIn("link/answer.txt",snap)
        self.fixture(check)

    def test_absolute_path_outside_task_workdir_stays_outside_scope(self):
        async def check(root,app,ctl,instance):
            target=root/"secret.txt";target.write_text("OUTSIDE")
            record=instance(f"Deliver {target}")
            self.assertNotIn("../secret.txt",await record.snapshot(save=False))
        self.fixture(check)

    def test_missing_named_path_is_not_fabricated(self):
        async def check(root,app,ctl,instance):
            record=instance(f"Deliver {app/'missing.txt'}")
            snap=await record.snapshot(save=False)
            self.assertNotIn("missing.txt",snap)
        self.fixture(check)

if __name__=="__main__":
    unittest.main(verbosity=2)
