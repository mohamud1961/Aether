"""Deterministic source-actual Core run-state finish tests; no model/benchmark/provider.

Import real runstate source with a fake sibling env to avoid optional infra deps.
"""
from __future__ import annotations
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/aether/core/runstate.py"
pkgname="_offline_runstate_fixture"
pkg=types.ModuleType(pkgname)
pkg.__path__=[str(SRC.parent)]
envmod=types.ModuleType(pkgname+".env")
class Env: pass
class Response:
    def __init__(self,code):self.code,self.stdout,self.stderr=code,"",""
run_invocations=[]
async def run(env,cmd,timeout_s,cwd):
    run_invocations.append((cmd,timeout_s,cwd))
    return Response(0 if cmd in ("true","test -s out.txt") else 1)
envmod.Environment=Env
envmod.run=run
sys.modules[pkgname]=pkg
sys.modules[pkgname+".env"]=envmod
spec=importlib.util.spec_from_file_location(pkgname+".runstate",SRC)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

TASK="Write a full report to out.txt.\n- The final report must include all required results."
def state():
    return mod.RunState(TASK,"/working",clock=lambda:0.0)

class CoreStateNoPhantomFinishHold(unittest.TestCase):
    def setUp(self):run_invocations.clear()
    def finish(self,s,remaining=600,timeout=900):
        return asyncio.run(s.at_finish(Env(),remaining_s=remaining,timeout_s=timeout))
    def act(self,s,**kwargs):
        return asyncio.run(s.act(Env(),kwargs,remaining_s=600))
    def test_empty_optional_state_first_finish_not_held(self):
        s=state()
        held,text=self.finish(s)
        self.assertFalse(held,"optional uninitialized state must not veto genuine finish")
        self.assertEqual(text,"")
        self.assertFalse(s.held)
        self.assertTrue(s.final_checked)
        self.assertEqual(run_invocations,[])
    def test_notes_only_state_does_not_create_fake_requirement_blocker(self):
        s=state()
        self.assertIn("noted",self.act(s,action="note",text="actual result at out.txt"))
        self.assertFalse(self.finish(s)[0])
        self.assertIn("actual result",s.account())
    def test_viewing_state_only_never_creates_finish_hold(self):
        s=state()
        self.act(s,action="show")
        self.assertFalse(self.finish(s)[0])
    def test_repeated_finish_without_require_does_not_create_hold(self):
        s=state()
        self.assertFalse(self.finish(s)[0]);self.assertFalse(self.finish(s)[0])
        self.assertEqual(len([e for e in s.events if e["action"]=="finish"]),2)
    def test_negative_missing_task_coverage_no_tool_item_is_reported_not_gate(self):
        s=state()
        self.assertGreater(len(s.uncovered()),0)
        self.assertFalse(self.finish(s)[0])
        self.assertIn("no requirements were recorded",s.account())
    def test_explicit_failed_requirement_still_holds_once(self):
        s=state()
        q="must include all required results"
        self.assertIn("added",self.act(s,action="require",quote=q,check="false"))
        held,text=self.finish(s)
        self.assertTrue(held)
        self.assertIn("#1 failed",text)
        self.assertFalse(self.finish(s)[0])
        self.assertEqual(len(run_invocations),2)
    def test_explicit_unchecked_requirement_still_holds_once(self):
        s=state()
        self.act(s,action="require",quote="must include all required results")
        held,text=self.finish(s)
        self.assertTrue(held)
        self.assertIn("unchecked",text)
        self.assertEqual(run_invocations,[])
    def test_time_low_allows_finish_without_hold(self):
        s=state();self.act(s,action="require",quote="must include all required results",check="false")
        self.assertFalse(self.finish(s,remaining=50)[0])
        self.assertTrue(s.final_checked)
    def test_explicit_valid_check_reruns_at_finish(self):
        s=state()
        self.act(s,action="require",quote="must include all required results",check="true")
        self.finish(s)
        self.assertEqual(s.items[0].status,"passed")
        self.assertEqual(len(run_invocations),1)
    def test_wrong_initial_id_is_not_silently_creation(self):
        s=state()
        ans=self.act(s,action="require",id=1,quote="must include all required results",check="true")
        self.assertTrue(ans.startswith("error:"))
        self.assertEqual(len(s.items),0)
    def test_correct_initial_create_then_explicit_replace(self):
        s=state()
        self.act(s,action="require",quote="must include all required results",check="false")
        r=self.act(s,action="require",id=1,check="true")
        self.assertIn("check replaced",r)
        self.assertEqual(s.items[0].check,"true")
    def test_unsupported_action_refused_not_success(self):
        s=state()
        self.assertTrue(self.act(s,action="invent").startswith("error:"))
        self.assertFalse(self.finish(s)[0])
    def test_whole_task_correct_not_implied_by_state_finish(self):
        s=state()
        self.assertFalse(self.finish(s)[0])
        self.assertNotIn("contract_correct",s.record())
if __name__=="__main__":unittest.main(verbosity=2)
