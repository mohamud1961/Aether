"""Mechanical replay of production loop._run_calls, without provider dependencies.

Extracts exact production AST, supplies deterministic scripted tool outcomes.
No model, network, GPU, task evaluator or installed pytest required.
"""
from __future__ import annotations

import os
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

SOURCE = Path(os.environ.get("AETHER_CORE_TEST_PACKAGE_ROOT", Path(__file__).resolve().parents[1] / "src/aether/core")) / "loop_calls.py"
TREE = ast.parse(SOURCE.read_text())
FUNCTION = next(x for x in TREE.body if isinstance(x, ast.AsyncFunctionDef) and x.name == "_run_calls")
EVENTS = []
ENV_CHECKS = []

async def fake_invoke(s, call):
    name=call["function"]["name"]
    label=call.get("label",name)
    EVENTS.append(("start",label))
    if call.get("sleep"):
        await asyncio.sleep(call["sleep"])
    EVENTS.append(("end",label))
    out=call.get("out",f"ok:{label}")
    return call.get("args",{}),out,name=="finish",0.001,False

async def fake_save(s,output):
    return output

async def require(s):
    ENV_CHECKS.append("probe")
    if getattr(s, "probe_failure",False):
        raise RuntimeError("environment not confirmed")

def append(s,*messages):
    s.messages.extend(messages)

SCOPE={
    "asyncio":asyncio,
    "_invoke":fake_invoke,
    "_save":fake_save,
    "_require_environment":require,
    "_append":append,
    "_action_view":lambda name,args,out:(name,args,out),
    "finish_report":NS(record=lambda step,name,args,out,wd:(step,name,args,out)),
}
exec(compile(ast.fix_missing_locations(ast.Module(body=[FUNCTION],type_ignores=[])),str(SOURCE),"exec"),SCOPE)
run_calls=SCOPE["_run_calls"]

def fake_session(*,parallel=False):
    out=NS(steps=0)
    s=NS(
        clm=None,config=NS(parallel_reads=parallel),
        result=out,actions=[],report_steps=[],workdir="/workspace",
        trace=lambda event,**fields:EVENTS.append(("trace",fields.get("name","?"))),
        record=None,diffcheck=None,state=None,facts=None,pending_images=[],
        messages=[],clock=lambda:"[time remaining test]",env=None,
    )
    return s

def call(name,label,out=None,delay=0.0):
    result={"id":f"id-{label}","label":label,
            "function":{"name":name,"arguments":"{}"},"sleep":delay}
    if out is not None:result["out"]=out
    return result

class ScriptedCallReplay(unittest.TestCase):
    def setUp(self):
        EVENTS.clear()
        ENV_CHECKS.clear()

    def test_tool_call_results_use_original_ids_and_order(self):
        s=fake_session()
        calls=[call("read_file","a"),call("write_file","b"),call("terminal","c")]
        complete=asyncio.run(run_calls(s,calls))
        self.assertFalse(complete)
        self.assertEqual([m["tool_call_id"] for m in s.messages], [x["id"] for x in calls])
        self.assertEqual(s.result.steps,3)
        self.assertEqual([a[0] for a in s.actions],["read_file","write_file","terminal"])
        self.assertEqual(ENV_CHECKS,[])

    def test_same_turn_error_before_finish_forces_environment_probe(self):
        s=fake_session()
        calls=[call("terminal","bad","error: child exited"),call("finish","done")]
        complete=asyncio.run(run_calls(s,calls))
        self.assertTrue(complete)
        self.assertEqual(ENV_CHECKS,["probe"])
        self.assertEqual([m["tool_call_id"] for m in s.messages],["id-bad","id-done"])

    def test_error_probe_refusal_prevents_finish(self):
        s=fake_session()
        s.probe_failure=True
        calls=[call("terminal","bad","error: storage lost"),call("finish","done")]
        with self.assertRaisesRegex(RuntimeError,"not confirmed"):
            asyncio.run(run_calls(s,calls))
        self.assertEqual(ENV_CHECKS,["probe"])
        self.assertEqual([m["tool_call_id"] for m in s.messages],["id-bad"])

    def test_parallel_read_result_order_is_preserved(self):
        s=fake_session(parallel=True)
        calls=[call("read_file","slow",delay=.07),call("read_file","fast",delay=.002)]
        asyncio.run(run_calls(s,calls))
        self.assertEqual([m["tool_call_id"] for m in s.messages],["id-slow","id-fast"])
        starts=[name for action,name in EVENTS if action=="start"]
        self.assertEqual(starts,["slow","fast"])

    def test_parallel_read_barrier_never_crosses_write(self):
        s=fake_session(parallel=True)
        calls=[call("read_file","r1",delay=.01),call("read_file","r2",delay=.02),
               call("write_file","write"),call("read_file","r3")]
        asyncio.run(run_calls(s,calls))
        events=[(action,name) for action,name in EVENTS if action in ("start","end")]
        self.assertLess(events.index(("end","r2")),events.index(("start","write")))
        self.assertLess(events.index(("end","write")),events.index(("start","r3")))
        self.assertEqual([m["tool_call_id"] for m in s.messages],[x["id"] for x in calls])

    def test_failed_non_finish_turn_probes_environment_once(self):
        s=fake_session()
        asyncio.run(run_calls(s,[call("terminal","bad","error: no command")]))
        self.assertEqual(ENV_CHECKS,["probe"])
        self.assertEqual(len(s.messages),1)

    def test_finish_without_error_can_finish_no_extra_probe(self):
        s=fake_session()
        finish=asyncio.run(run_calls(s,[call("finish","done")]))
        self.assertTrue(finish)
        self.assertEqual(ENV_CHECKS,[])
        self.assertEqual(len(s.messages),1)


if __name__=="__main__":
    unittest.main(verbosity=2)
