"""Source-actual CLM nudge claims: context footprint is not free inference."""
import os
import ast
from pathlib import Path
import types
import unittest

FILE=Path(os.environ.get("AETHER_CORE_TEST_PACKAGE_ROOT", Path(__file__).resolve().parents[1]/"src/aether/core"))/"clm.py"
module=ast.parse(FILE.read_text())
cls=next(x for x in module.body if isinstance(x,ast.ClassDef) and x.name=="ClmContext")
method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=="nudge")
ns={"URGENT_EVERY_TURNS":3}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(FILE),"exec"),ns)
nudge=ns["nudge"]
class Stub:
    def __init__(self,used,budget,threshold=0.5):
        self.usage=used
        self.settings=types.SimpleNamespace(budget_tokens=budget,limit=budget-2048,mirror_path="/tmp/ctx")
        self.stats=types.SimpleNamespace(max_tokens_seen=0,nudges=0,urgent_nudges=0)
        self._recent_outputs=[]
        self.chars_per_token=3.0
        self._turn=0
        self._last_urgent=-3
        self._armed={threshold,0.75}
    def held(self):return self.usage
    def tokens(self):return self.usage
    def _rearm(self,ratio):return None

class ClmCostClaim(unittest.TestCase):
    def test_normal_nudge_never_claims_turn_is_free(self):
        v=Stub(16000,32000)
        result=nudge(v)
        self.assertIn("context",result)
        self.assertNotIn(" is free",result.lower())
        self.assertIn("token",result.lower())
    def test_normal_nudge_explains_model_cost_not_elided(self):
        v=Stub(16000,32000)
        result=nudge(v).lower()
        self.assertTrue("still" in result and "token" in result,
                        "must distinguish context footprint from inference cost")
    def test_high_ratio_urgent_nudge_unchanged(self):
        v=Stub(29500,32000)
        self.assertIn("[context: urgent]",nudge(v))
    def test_below_threshold_no_extra_prompt(self):
        v=Stub(2000,32000)
        self.assertEqual(nudge(v),"")
    def test_crossed_threshold_is_one_shot(self):
        v=Stub(16000,32000)
        self.assertTrue(nudge(v))
        self.assertFalse(nudge(v))
    def test_no_provider_calls_are_added(self):
        v=Stub(16000,32000)
        self.assertIsInstance(nudge(v),str)
        self.assertEqual(v.stats.nudges,1)
if __name__=="__main__":unittest.main(verbosity=2)
