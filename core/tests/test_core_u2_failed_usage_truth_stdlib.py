"""Failed/partial provider calls cannot assert exact total billed token usage.

No provider/model/task run: CallLog receives synthetic reported attempt fields.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from aether.core.calls import CallLog

COMPLETE={"input":100,"cached":20,"output":40,"reasoning":5}

def ended(log,role,ok,usage):
    seq=log.start(role=role,attempt=1,request={"messages":[{"role":"user","content":"synthetic"}]})
    log.end(seq,{"ok":ok,"usage":dict(usage),"response":{"content":"","reasoning":"","tool_calls":[]}})
    return seq

class FailedAttemptUsage(unittest.TestCase):
    def test_completed_success_with_reported_usage_remains_known(self):
        log=CallLog()
        ended(log,"worker",True,COMPLETE)
        self.assertEqual(log.usage(["worker"]),COMPLETE)
        self.assertEqual(log.totals()["worker"]["usage_unknown"],0)

    def test_failed_attempt_with_full_fields_must_make_totals_unknown(self):
        log=CallLog()
        ended(log,"worker",False,COMPLETE)
        self.assertEqual(log.usage(["worker"]),{k:None for k in COMPLETE})
        self.assertGreater(log.totals()["worker"]["usage_unknown"],0)
        # The provider-reported partial figures remain in auditable lower-
        # confidence arithmetic; they are never promoted to exact total cost.
        self.assertEqual(log.totals()["worker"]["input"],100)

    def test_prior_good_plus_failed_full_usage_still_unknown(self):
        log=CallLog()
        ended(log,"worker",True,COMPLETE)
        ended(log,"worker",False,COMPLETE)
        self.assertIsNone(log.usage(["worker"])["input"])
        self.assertIsNone(log.usage(["worker"])["output"])

    def test_unrelated_role_not_poisoned_by_other_failed_attempt(self):
        log=CallLog()
        ended(log,"reviewer",True,COMPLETE)
        ended(log,"worker",False,COMPLETE)
        self.assertEqual(log.usage(["reviewer"]),COMPLETE)
        self.assertIsNone(log.usage(["worker"])["input"])

    def test_cancelled_partial_attempt_is_unknown_even_when_all_fields_reported(self):
        log=CallLog()
        seq=log.start(role="worker",attempt=1,request={"messages":[]})
        log.end(seq,{"ok":False,"error":"cancelled","usage":COMPLETE,
                     "response":{"content":"partial","reasoning":"","tool_calls":[]}})
        self.assertIsNone(log.usage()["input"])
        self.assertEqual(log.totals()["worker"]["cancelled"],1)

    def test_open_attempt_keeps_exact_totals_unknown(self):
        log=CallLog()
        ended(log,"worker",True,COMPLETE)
        log.start(role="worker",attempt=2,request={"messages":[]})
        self.assertIsNone(log.usage()["output"])

    def test_log_retains_actual_partial_usage_and_uncertainty_reason(self):
        from tempfile import TemporaryDirectory
        from aether.core.calls import requests
        with TemporaryDirectory(prefix="aether-usage-") as folder:
            log=CallLog(Path(folder)/"calls.jsonl")
            ended(log,"worker",False,COMPLETE)
            (entry,)=tuple(requests(Path(folder)/"calls.jsonl"))
            self.assertEqual(entry["usage"],COMPLETE)
            self.assertEqual(entry["usage_certainty"],"incomplete_attempt")
            self.assertEqual(entry["usage_missing"],[])
            self.assertFalse(entry["ok"])
            self.assertIsNone(log.usage()["input"])

    def test_successful_reported_usage_certainty(self):
        from tempfile import TemporaryDirectory
        from aether.core.calls import requests
        with TemporaryDirectory(prefix="aether-usage-") as folder:
            log=CallLog(Path(folder)/"calls.jsonl")
            ended(log,"worker",True,COMPLETE)
            (entry,)=tuple(requests(Path(folder)/"calls.jsonl"))
            self.assertEqual(entry["usage_certainty"],"fully_reported_success")

    def test_missing_reported_usage_field_still_unknown(self):
        log=CallLog()
        ended(log,"worker",True,{"input":5,"output":4})
        # The prompt input token field was explicitly reported by a
        # successful call, and is still useful. Missing cache/reasoning
        # remain unknown; do not erase independent observed metrics.
        self.assertEqual(log.usage()["input"],5)
        self.assertEqual(log.usage()["output"],4)
        self.assertIsNone(log.usage()["cached"])
        self.assertIsNone(log.usage()["reasoning"])

if __name__=="__main__":
    unittest.main(verbosity=2)
