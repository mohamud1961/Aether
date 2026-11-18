"""Actual verify.at_finish AST exercised with synthetic no-provider clone/review results.

No model, sandbox, grader, benchmark or paid infrastructure. The async source
is compiled from real production file; all external I/O functions are fakes.
"""
from __future__ import annotations
import os
import ast
import asyncio
from pathlib import Path
import time
import types
import typing
import unittest

FILE=Path(os.environ.get("AETHER_CORE_TEST_PACKAGE_ROOT", Path(__file__).resolve().parents[1]/"src/aether/core"))/"verify.py"
TREE=ast.parse(FILE.read_text())
def original(name):
    found=[n for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    assert len(found)==1,name
    return found[0]
class DummyResult:
    status="finished"
    error=""
    steps=1
    def __init__(self,verdict):
        self.extras={"finish_args":{"verdict":verdict,"evidence":"test-visible observation bound to candidate"}}
class DummySession:
    def __init__(self):
        self.result=types.SimpleNamespace(extras={})
        self.provider=types.SimpleNamespace(log=types.SimpleNamespace())
        self.pending_cleanup=[]
        self.rows=[]
    def remaining(self):
        return 600.0
    def trace(self,*args,**kwargs):pass

def run_case(verdict,*,unbound=False,missing_manifest=False,writable=False,
             changed=False,original_changed=False,review_error=False,partial=False):
    def make_review(s,row,held,work_end,manifest_s):
        async def review():
            if review_error:
                row["reason"]="faked review failure"
                return
            if not missing_manifest:
                row["clone_changes"]={"modified":["bad.py"] if changed else [],
                                      "deleted":[],"created":[]}
            row["boundary"]="writable" if writable else "read_only"
            if unbound:row["binding_unavailable"]=["unavailable file snapshot"]
            if original_changed:row["original_changed"]=True
            if partial:row["unbound"]=["external mount"]
            held["result"]=DummyResult(verdict)
        return review()
    async def no_close(*args,**kwargs):return None
    session=DummySession()
    ns={
        "asyncio":asyncio,"time":time,"Any":typing.Any,
        "VERIFY_MIN_REMAINING_S":180.0,"VERIFY_MAX_S":600.0,"VERIFY_SHARE":0.4,
        "CLEANUP_SHARE":0.25,"CLEANUP_MAX_S":30.0,"MANIFEST_SHARE":0.15,
        "MANIFEST_MAX_S":60.0,
        "MAX_LISTED":60,"MAX_EVIDENCE_CHARS":8000,
        "DEFECT":"[defect held] {evidence}",
        "MODIFIED":"[clone modified] {files}: {evidence}",
        "UNBOUND_NOTE":"[unbound evidence]",
        "_review":make_review,"_close":no_close,
        "_record":lambda s,row:s.rows.append(dict(row)),
        "_usage":lambda provider:{"unknown_cost":None},
        "_hand_off":lambda *args:None
    }
    # Execute actual _status and _finding (not a hand-written reconstruction),
    # followed by actual at_finish. Stub only external model/clone functions.
    handback_env = next(
        node for node in TREE.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "HANDBACK_ENV" for target in node.targets)
    )
    ns["os"] = types.SimpleNamespace(environ={})
    src=ast.Module(body=[handback_env, original("_handback"), original("_finding"),
                         original("_status"), original("at_finish")],type_ignores=[])
    ast.fix_missing_locations(src)
    exec(compile(src,str(FILE),"exec"),ns)
    return asyncio.run(ns["at_finish"](session)),session

class CoreVerifierSourceBinding(unittest.TestCase):
    def test_fully_bound_readonly_source_defect_still_holds_once(self):
        (message,finished),s=run_case("defect_found")
        self.assertFalse(finished)
        self.assertIn("defect held",message)
        self.assertEqual(s.rows[0]["status"],"defect_found")
    def test_missing_manifest_defect_must_not_veto_task_finish(self):
        (message,finished),s=run_case("defect_found",missing_manifest=True)
        self.assertTrue(finished)
        self.assertIn("unbound",s.rows[0]["status"])
    def test_explicit_binding_unavailable_cannot_veto(self):
        (message,finished),s=run_case("defect_found",unbound=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"defect_found_unbound")
    def test_unbound_writable_clone_cannot_veto(self):
        (message,finished),s=run_case("defect_found",unbound=True,writable=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"defect_found_unbound_writable")
    def test_partial_tree_on_a_held_readonly_clone_holds_once(self):
        (message,finished),s=run_case("defect_found",partial=True)
        self.assertFalse(finished)
        self.assertIn("defect held",message)
        self.assertEqual(s.rows[0]["status"],"defect_found")
    def test_writable_clone_cannot_veto(self):
        (message,finished),s=run_case("defect_found",writable=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"defect_found_writable")
    def test_writable_partial_clone_cannot_veto(self):
        (message,finished),s=run_case("defect_found",writable=True,partial=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"defect_found_partial_writable")
    def test_bound_checker_no_defect_finishes(self):
        (_,finished),s=run_case("no_defect_found")
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"no_defect_found")
    def test_missing_manifest_no_defect_remains_unknown_but_finishes(self):
        (_,finished),s=run_case("no_defect_found",missing_manifest=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"no_defect_found_unbound")
    def test_unknown_verdict_finishes(self):
        (_,finished),s=run_case("undetermined")
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"undetermined")
    def test_void_verifier_mutated_its_own_clone_remains_held(self):
        (message,finished),s=run_case("defect_found",changed=True)
        self.assertFalse(finished)
        self.assertIn("clone modified",message)
        self.assertEqual(s.rows[0]["status"],"void_candidate_modified")
    def test_original_changed_during_review_finishes(self):
        (_,finished),s=run_case("defect_found",original_changed=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"stale_original_changed")
    def test_review_error_finishes(self):
        (_,finished),s=run_case("defect_found",review_error=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"error")
    def test_unknown_verdict_with_unbound_manifest_finishes(self):
        (_,finished),s=run_case(None,missing_manifest=True)
        self.assertTrue(finished)
        self.assertEqual(s.rows[0]["status"],"no_finding")
    def test_verifier_report_records_unbound_status_not_literal_truth(self):
        (_,finished),s=run_case("defect_found",missing_manifest=True)
        self.assertTrue(finished)
        self.assertNotIn("contract_correct",s.rows[0])
    def test_source_contains_one_nonmandatory_verifier_pass(self):
        method=original("at_finish")
        self.assertEqual(method.name,"at_finish")
        # Verify it retains the external late/report machinery in source.
        txt=ast.dump(method)
        self.assertIn("at_finish",txt)
        self.assertIn("_record",txt)
if __name__=="__main__":
    unittest.main(verbosity=2)
