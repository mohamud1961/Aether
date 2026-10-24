"""Core F4 actual env.py + files.py local FS tests (synthetic only).

Runs shell commands only in isolated tempfile via fake Harbor-like environment.
No provider, model, benchmark, service or paid infrastructure.
"""
from __future__ import annotations
import asyncio
import importlib.util
import hashlib
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/aether/core"
PKG="_core_f4_test_package"
pkg=types.ModuleType(PKG);pkg.__path__=[str(SRC)]
sys.modules[PKG]=pkg
def load(name):
    spec=importlib.util.spec_from_file_location(PKG+"."+name,SRC/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

env=load("env")
files_mod=load("files")

class LocalSandbox:
    def __init__(self, root, mutate=None):
        self.root=Path(root)
        self.mutate=mutate
        self.triggered=False
        self.commands=[]
        self.uploaded=0
        self.downloaded=0
    async def exec(self,command,cwd=None,env=None,timeout_sec=None):
        self.commands.append(command)
        if self.mutate and not self.triggered:
            mode,change=self.mutate
            if (mode=="before_mode" and "stat -Lc %a" in command) or (
                mode=="before_commit" and "mv -fT" in command
            ):
                change(self.root/"doc.txt")
                self.triggered=True
        try:
            p=subprocess.run(["/bin/sh","-c",command],
                cwd=cwd or str(self.root),capture_output=True,text=True,
                timeout=timeout_sec or 30)
            return types.SimpleNamespace(exit_code=p.returncode,
                                         stdout=p.stdout,stderr=p.stderr)
        except subprocess.TimeoutExpired as exc:
            return types.SimpleNamespace(exit_code=124,stdout="",stderr=str(exc))
    async def upload_file(self,source_path,target_path):
        self.uploaded+=1
        shutil.copyfile(source_path,target_path)
    async def download_file(self,source_path,target_path):
        self.downloaded+=1
        shutil.copyfile(source_path,target_path)

class RealSourceLocalConflict(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="aether-f4-local-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.target=self.root/"doc.txt"
        self.target.write_text("ORIGINAL\n")
        self.env=LocalSandbox(self.root)
        self.files=files_mod.Files(self.env,str(self.root))
    def go(self,co):return asyncio.run(co)
    def edit(self,old="ORIGINAL",new="MODEL_NEW"):
        return self.go(self.files.edit("doc.txt",old,new))
    def self_mutation(self,mode,change):
        self.env=LocalSandbox(self.root,(mode,change))
        self.files=files_mod.Files(self.env,str(self.root))
    def tmp_is_clean(self):
        self.assertEqual(list(self.root.glob("doc.txt.aether-*.tmp")),[])
    def test_real_local_valid_edit_and_exact_persisted_bytes(self):
        result=self.edit()
        self.assertEqual(self.target.read_bytes(),b"MODEL_NEW\n")
        self.assertIn("edited",result)
        self.assertIn("MODEL_NEW",result)
        self.tmp_is_clean()
    def test_existing_new_str_does_not_change_receipt_anchor(self):
        self.target.write_text("MODEL_NEW above\n"+("gap\n"*8)+"ORIGINAL below\n")
        out=self.edit()
        self.assertIn("    10  MODEL_NEW below",out)
        self.assertNotIn("     1  MODEL_NEW above",out)
    def test_race_before_mode_does_not_overwrite_other_writer(self):
        self.self_mutation("before_mode",lambda p:p.write_text("OTHER_WRITER\n"))
        with self.assertRaisesRegex(OSError,"conflict"):
            self.edit()
        self.assertTrue(self.env.triggered)
        self.assertEqual(self.target.read_bytes(),b"OTHER_WRITER\n")
        self.tmp_is_clean()
    def test_race_after_staging_before_commit_refused(self):
        self.self_mutation("before_commit",lambda p:p.write_text("OTHER_WRITER\n"))
        with self.assertRaisesRegex(OSError,"conflict"):
            self.edit()
        self.assertTrue(self.env.triggered)
        self.assertEqual(self.target.read_bytes(),b"OTHER_WRITER\n")
        self.tmp_is_clean()
    def test_deleted_target_before_commit_not_recreated(self):
        self.self_mutation("before_commit",lambda p:p.unlink())
        with self.assertRaisesRegex(OSError,"conflict"):
            self.edit()
        self.assertFalse(self.target.exists())
        self.tmp_is_clean()
    def test_changed_permissions_before_commit_refused(self):
        self.target.chmod(0o750)
        self.self_mutation("before_commit",lambda p:p.chmod(0o700))
        with self.assertRaisesRegex(OSError,"conflict"):
            self.edit()
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode),0o700)
        self.assertEqual(self.target.read_text(),"ORIGINAL\n")
        self.tmp_is_clean()
    def test_exact_edit_preserves_original_executable_permissions(self):
        self.target.chmod(0o751)
        self.edit()
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode),0o751)
    def test_unconditional_write_file_still_overwrites_by_user_choice(self):
        self.go(self.files.write("doc.txt","DIRECT_NEW"))
        self.assertEqual(self.target.read_bytes(),b"DIRECT_NEW")
        self.tmp_is_clean()
    def test_direct_put_bytes_default_unconditional(self):
        self.go(env.put_bytes(self.env,b"DIRECT_BYTES",str(self.target)))
        self.assertEqual(self.target.read_bytes(),b"DIRECT_BYTES")
        self.tmp_is_clean()
    def test_wrong_precondition_is_denied_before_write(self):
        with self.assertRaisesRegex(OSError,"conflict"):
            self.go(env.put_bytes(self.env,b"MODEL_NEW",str(self.target),expected_sha256="0"*64))
        self.assertEqual(self.target.read_text(),"ORIGINAL\n")
        self.tmp_is_clean()
    def test_correct_precondition_commits(self):
        h=hashlib.sha256(self.target.read_bytes()).hexdigest()
        self.go(env.put_bytes(self.env,b"MODEL_NEW",str(self.target),expected_sha256=h))
        self.assertEqual(self.target.read_bytes(),b"MODEL_NEW")
    def test_malformed_hash_is_rejected_with_no_action(self):
        before=len(self.env.commands)
        with self.assertRaisesRegex(ValueError,"expected_sha256"):
            self.go(env.put_bytes(self.env,b"MODEL_NEW",str(self.target),expected_sha256="notsha"))
        self.assertEqual(len(self.env.commands),before)
        self.assertEqual(self.target.read_text(),"ORIGINAL\n")
    def test_content_in_long_staged_upload_preserves_precondition(self):
        h=hashlib.sha256(self.target.read_bytes()).hexdigest()
        body=b"x"*50000
        self.go(env.put_bytes(self.env,body,str(self.target),expected_sha256=h))
        self.assertEqual(self.target.read_bytes(),body)
        self.assertEqual(self.env.uploaded,1)
        self.tmp_is_clean()
    def test_file_tool_failed_pattern_preserves_f3_byte_evidence(self):
        with self.assertRaisesRegex(ValueError,"observed read-time sha256=") as ctx:
            self.edit("ORIGINAL \n missing", "something")
        self.assertIn(hashlib.sha256(b"ORIGINAL\n").hexdigest(),str(ctx.exception))
        self.assertEqual(self.target.read_bytes(),b"ORIGINAL\n")
    def test_file_tool_ambiguous_pattern_remains_refused(self):
        self.target.write_text("ORIGINAL\nORIGINAL\n")
        with self.assertRaisesRegex(ValueError,"occurs 2 times"):
            self.edit()
        self.assertEqual(self.target.read_text(),"ORIGINAL\nORIGINAL\n")
    def test_single_read_of_source_observed_for_exact_edit(self):
        self.edit()
        self.assertEqual(self.env.downloaded,1)
    def test_precondition_only_on_edits_not_ordinary_writes(self):
        self.go(self.files.write("doc.txt","REPLACEMENT"))
        self.assertFalse(any("edit conflict" in c for c in self.env.commands))
    def test_failed_conflict_does_not_claim_successful_file_write(self):
        self.self_mutation("before_commit",lambda p:p.write_text("OTHER_WRITER"))
        with self.assertRaisesRegex(OSError,"conflict"):
            self.edit()
        self.assertFalse(self.files.written)
if __name__=="__main__":
    unittest.main(verbosity=2)
