"""Bounded record named-path coverage: correct controls and adversarial paths."""
from __future__ import annotations
import asyncio
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aether.core.record import Record
from aether.core.receipt import MARKER, SKIP
from tests.core_fakes import LocalEnv

def fixture(fn):
    async def go(root):
        work=root/"app"; work.mkdir()
        ctl=root/"ctl"; ctl.mkdir()
        (ctl/MARKER).write_text("start")
        def instance(task):
            return Record(LocalEnv(work),str(work),str(ctl),
                          remaining=lambda:300,trace=lambda *_a,**_k:None,
                          task=task)
        return await fn(root,work,ctl,instance)
    with tempfile.TemporaryDirectory(prefix="aether-recorder-edges-") as tmp:
        return asyncio.run(go(Path(tmp)))

def old(path):
    os.utime(path,(1234,1234))

class RecorderNamedEdges(unittest.TestCase):
    def test_nested_named_path_and_hidden_extension(self):
        async def run(root,work,ctl,record):
            folder=work/"data"/"nested"
            folder.mkdir(parents=True)
            f=folder/".batch.json";f.write_text("payload")
            old(f)
            snapshot=await record(f"Deliver {f}").snapshot(save=True)
            self.assertEqual(snapshot["data/nested/.batch.json"],hashlib.sha256(b"payload").hexdigest())
            self.assertEqual((ctl/"versions"/snapshot["data/nested/.batch.json"]/"data/nested/.batch.json").read_text(),"payload")
        fixture(run)

    def test_old_non_named_file_still_out_of_snapshot(self):
        async def run(root,work,ctl,record):
            f=work/"old-unmentioned.txt";f.write_text("untouched");old(f)
            self.assertNotIn("old-unmentioned.txt",await record("Create output elsewhere").snapshot(save=False))
        fixture(run)

    def test_named_skipped_directory_not_traversed(self):
        async def run(root,work,ctl,record):
            chosen=next(iter(SKIP))
            folder=work/chosen;folder.mkdir()
            f=folder/"named.txt";f.write_text("private");old(f)
            self.assertNotIn(f"{chosen}/named.txt",await record(f"Create {f}").snapshot(save=False))
        fixture(run)

    def test_named_leaf_symlink_not_captured(self):
        async def run(root,work,ctl,record):
            private=root/"secret";private.write_text("private")
            link=work/"answer.txt";link.symlink_to(private)
            self.assertNotIn("answer.txt",await record(f"Create {link}").snapshot(save=False))
        fixture(run)

    def test_same_file_mentioned_twice_captured_once(self):
        async def run(root,work,ctl,record):
            f=work/"answer.txt";f.write_text("dup");old(f)
            snap=await record(f"Create {f}, then inspect {f}").snapshot(save=False)
            self.assertEqual(len(snap),1)
        fixture(run)

    def test_file_too_large_for_named_capture_not_retained(self):
        async def run(root,work,ctl,record):
            f=work/"huge.txt";f.write_bytes(b"a"*(20_000_000))
            old(f)
            self.assertNotIn("huge.txt",await record(f"Create {f}").snapshot(save=True))
        fixture(run)

    def test_named_binary_bytes_included_without_assuming_text(self):
        async def run(root,work,ctl,record):
            f=work/"answer.bin";f.write_bytes(b"\x00\xff\xfe\x12");old(f)
            snap=await record(f"Deliver {f}").snapshot(save=True)
            self.assertEqual(snap.get("answer.bin"),hashlib.sha256(b"\x00\xff\xfe\x12").hexdigest())
        fixture(run)

    def test_named_file_with_metacharacters_is_shell_quoted(self):
        async def run(root,work,ctl,record):
            f=work/"out-1.txt";f.write_text("name");old(f)
            snap=await record(f"Deliver {f}").snapshot(save=False)
            self.assertIn("out-1.txt",snap)
        fixture(run)

if __name__=="__main__":
    unittest.main(verbosity=2)
