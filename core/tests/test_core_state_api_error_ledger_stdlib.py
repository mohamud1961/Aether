"""Actual Core state API error receipts; source-loaded without provider or task execution."""
import asyncio
import unittest
from test_core_state_no_empty_hold_stdlib import state,mod,Env

def act(s,**kwargs):return asyncio.run(s.act(Env(),kwargs,remaining_s=600))

class StateActionErrorProvenance(unittest.TestCase):
    def test_error_is_logged_in_run_state_without_pretending_success(self):
        s=state()
        err=act(s,action="require",id=1,quote="must include all required results",check="true")
        self.assertTrue(err.startswith("error:"))
        self.assertEqual(len(s.events),1,"error actions must remain observable in independent state ledger")
        self.assertFalse(s.events[0]["ok"])
        self.assertEqual(s.events[0]["action"],"require")
        self.assertEqual(s.events[0]["id"],1)
        self.assertEqual(s.items,[])
    def test_failed_check_without_id_gets_corrective_hint_and_audit(self):
        s=state()
        err=act(s,action="check")
        self.assertTrue(err.startswith("error:"))
        self.assertIn("first",err.lower())
        self.assertIn("omit id",err.lower())
        self.assertEqual(s.events[0]["ok"],False)
    def test_valid_action_logged_as_success_once(self):
        s=state()
        v=act(s,action="show")
        self.assertIn("[state]",v)
        self.assertEqual(len(s.events),1)
        self.assertTrue(s.events[0]["ok"])
    def test_tool_description_says_do_not_set_id_for_create(self):
        schema=mod.STATE_TOOL["function"]["parameters"]["properties"]
        self.assertIn("omit",schema["id"]["description"].lower())
        self.assertIn("new",schema["id"]["description"].lower())
        self.assertIn("id",mod.STATE_TOOL["function"]["description"].lower())
    def test_success_then_error_preserves_event_order(self):
        s=state()
        act(s,action="note",text="file at /working/out.txt")
        act(s,action="require",id=9,quote="must include all required results",check="false")
        self.assertEqual([e["ok"] for e in s.events],[True,False])
    def test_invalid_id_never_modifies_existing_required_checks(self):
        s=state()
        act(s,action="require",quote="must include all required results",check="true")
        act(s,action="require",id=999,check="false")
        self.assertEqual(s.items[0].check,"true")
        self.assertEqual([e["ok"] for e in s.events],[True,False])
    def test_state_record_exports_failed_tool_events(self):
        s=state()
        act(s,action="check",id=1)
        out=s.record()
        self.assertEqual(len(out["events"]),1)
        self.assertFalse(out["events"][0]["ok"])
    def test_invalid_action_not_silently_dropped(self):
        s=state()
        self.assertTrue(act(s,action="invent").startswith("error:"))
        self.assertFalse(s.events[0]["ok"])
    def test_model_chosen_valid_require_preserved(self):
        s=state()
        self.assertIn("added",act(s,action="require",quote="must include all required results",check="false"))
        self.assertEqual(len(s.items),1)
        self.assertTrue(s.events[0]["ok"])
    def test_result_strings_bounded_in_event_log(self):
        s=state()
        act(s,action="note",text="x"*1000)
        self.assertLessEqual(len(s.events[0]["result"]),200)
if __name__=="__main__":unittest.main(verbosity=2)
