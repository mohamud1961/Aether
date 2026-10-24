"""Test actual Core Files.edit source with an isolated in-memory file executor.

No Harbor/provider/model or external process, no benchmark.
"""
import asyncio
import hashlib
import importlib.util
from pathlib import Path
import sys
import types
import unittest

FILE=Path(__file__).resolve().parents[1]/"src/aether/core/files.py"
pkgname="_offline_files_fixture"
pkg=types.ModuleType(pkgname);pkg.__path__=[str(FILE.parent)]
envmod=types.ModuleType(pkgname+".env")
class Env:pass
STORED={}
WRITES=[]
async def get_bytes(env,path):
    if path not in STORED:raise FileNotFoundError(path)
    return STORED[path]
async def put_bytes(env,data,path,mode=None,expected_sha256=None):
    if expected_sha256 is not None:
        before=STORED.get(path)
        if before is None or hashlib.sha256(before).hexdigest()!=expected_sha256:
            raise OSError("edit conflict: file content changed before commit")
    WRITES.append((path,data,mode))
    STORED[path]=data
async def run(*args,**kw):raise AssertionError("no terminal allowed")
envmod.Environment=Env
envmod.get_bytes=get_bytes
envmod.put_bytes=put_bytes
envmod.run=run
sys.modules[pkgname]=pkg
sys.modules[pkgname+".env"]=envmod
spec=importlib.util.spec_from_file_location(pkgname+".files",FILE)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

class HonestEditSnippet(unittest.TestCase):
    def setUp(self):
        STORED.clear();WRITES.clear()
        self.files=mod.Files(Env(),"/task")
        async def mode(_path):return "755"
        self.files._mode=mode
    def seed(self,text):STORED["/task/artifact.txt"]=text.encode("utf-8")
    def edit(self,old,new,all=False):
        return asyncio.run(self.files.edit("artifact.txt",old,new,replace_all=all))
    def test_existing_new_text_earlier_does_not_hijack_edit_line(self):
        self.seed("SAME already existed\n"+("filler\n"*15)+"OLD at real location\n")
        reply=self.edit("OLD","SAME")
        self.assertIn("    17  SAME at real location",reply)
        self.assertNotIn("     1  SAME already existed",reply)
    def test_multi_line_replacement_existing_earlier_reports_actual_new_start(self):
        self.seed("NEW\nold block here\n"+("gap\n"*16)+"OLD\n")
        reply=self.edit("OLD","NEW\nsecond")
        self.assertIn("    19  NEW",reply)
        self.assertIn("    20  second",reply)
    def test_replace_all_starts_at_first_actual_match(self):
        self.seed("YES already\n"+("gap\n"*16)+"NO\nNO\n")
        reply=self.edit("NO","YES",True)
        self.assertIn("    18  YES",reply)
        self.assertIn("2 replacements",reply)
    def test_simple_edit_preserves_existing_functionality(self):
        self.seed("a\nb OLD c\nd\n")
        result=self.edit("OLD","NEW")
        self.assertIn("     2  b NEW c",result)
        self.assertEqual(STORED["/task/artifact.txt"],b"a\nb NEW c\nd\n")
    def test_mode_passed_unchanged_and_written_bytes(self):
        self.seed("OLD\n")
        self.edit("OLD","NEW")
        self.assertEqual(WRITES,[("/task/artifact.txt",b"NEW\n","755")])
        self.assertEqual(self.files.written["/task/artifact.txt"],4)
    def test_empty_newstr_delete_reports_actual_location(self):
        self.seed("x\nOLD\ny\n")
        out=self.edit("OLD","")
        self.assertIn("     2  ",out)
        self.assertEqual(STORED["/task/artifact.txt"],b"x\n\ny\n")
    def test_missing_old_text_never_writes(self):
        self.seed("a\nb\n")
        with self.assertRaisesRegex(ValueError,"old_str not found"):
            self.edit("NOT_THERE","NEW")
        self.assertFalse(WRITES)
    def test_ambiguous_old_text_requires_replace_all(self):
        self.seed("OLD\nOLD\n")
        with self.assertRaisesRegex(ValueError,"occurs 2 times"):
            self.edit("OLD","NEW")
        self.assertFalse(WRITES)
    def test_replace_all_edits_all_actual_bytes(self):
        self.seed("OLD\nOLD\n")
        self.edit("OLD","NEW",True)
        self.assertEqual(STORED["/task/artifact.txt"],b"NEW\nNEW\n")
    def test_invalid_utf8_source_rejected(self):
        STORED["/task/artifact.txt"]=b"a\xffOLD"
        with self.assertRaisesRegex(ValueError,"not UTF-8"):
            self.edit("OLD","NEW")
        self.assertFalse(WRITES)
    def test_empty_old_str_rejected(self):
        self.seed("anything")
        with self.assertRaisesRegex(ValueError,"old_str is empty"):
            self.edit("","new")
    def test_unicode_line_count_correct(self):
        self.seed("β\n"+("gap\n"*11)+"OLD Ω\n")
        out=self.edit("OLD","new")
        self.assertIn("    13  new Ω",out)
    def test_first_match_location_not_new_duplicate_at_top(self):
        self.seed("new\n"+("x\n"*14)+"Old\n")
        out=self.edit("Old","new")
        self.assertIn("    16  new",out)
        self.assertNotIn("     1  new",out)
if __name__=="__main__":unittest.main(verbosity=2)
