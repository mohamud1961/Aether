"""Tests for bounded evidence on Core exact-edit failure, no invented correction."""
import hashlib
import unittest
import test_core_edit_receipt_actual_location_stdlib as fixture
STORED,WRITES=fixture.STORED,fixture.WRITES

class ScopedEditMissEvidence(unittest.TestCase):
    def setUp(self):
        # Reuse the actual source-loaded in-memory file executor without
        # inheriting 13 unrelated test cases from its unittest class.
        self.under_test=fixture.HonestEditSnippet("test_simple_edit_preserves_existing_functionality")
        self.under_test.setUp()
    def seed(self,text):return self.under_test.seed(text)
    def edit(self,old,new,all=False):return self.under_test.edit(old,new,all)

    def test_partial_old_code_anchor_reports_real_observed_line(self):
        self.seed("header\n"+("filler\n"*10)+"def compute_expected_value(): return 42\n")
        expected=hashlib.sha256(STORED["/task/artifact.txt"]).hexdigest()
        with self.assertRaises(ValueError) as context:
            self.edit("def compute_expected_value(): return 43","def compute_expected_value(): return 44")
        msg=str(context.exception)
        self.assertIn(expected,msg)
        self.assertIn("def compute_expected_value(): return 42",msg)
        self.assertIn("line 12",msg)
        self.assertIn("observed",msg.lower())
        self.assertFalse(WRITES)
    def test_unrelated_missing_pattern_no_invented_candidate(self):
        self.seed("completely different\n")
        with self.assertRaises(ValueError) as e:
            self.edit("zebra_zebra_zebra","done")
        self.assertIn("old_str not found",str(e.exception))
        self.assertNotIn("suggested replacement",str(e.exception))
        self.assertFalse(WRITES)
    def test_long_old_str_has_bounded_error(self):
        self.seed("header "+("x"*3000)+"\n")
        with self.assertRaises(ValueError) as e:
            self.edit(("completely_missing_piece_"*1000),"new")
        self.assertLess(len(str(e.exception)),850)
    def test_long_source_line_bounded_in_hint(self):
        self.seed("prefix\n"+"long_anchored_unique_identifier"+"a"*5000+"\n")
        with self.assertRaises(ValueError) as e:
            self.edit("long_anchored_unique_identifier isn't present in this form","replacement")
        self.assertLess(len(str(e.exception)),850)
    def test_hash_is_read_time_not_durable_authority(self):
        self.seed("actual_new_value is present\n")
        with self.assertRaises(ValueError) as e:
            self.edit("actual_new_value is absent","changed")
        self.assertIn("observed",str(e.exception).lower())
        self.assertNotIn("durably",str(e.exception).lower())
        self.assertFalse(WRITES)
    def test_unchanged_missing_path_error_no_hash(self):
        with self.assertRaises(FileNotFoundError):
            self.edit("old_str","replacement")
        self.assertFalse(WRITES)
    def test_unchanged_invalid_utf8_no_misleading_hint(self):
        STORED["/task/artifact.txt"]=b"\xffidentifier"
        with self.assertRaisesRegex(ValueError,"not UTF-8"):
            self.edit("identifier","replacement")
        self.assertFalse(WRITES)
    def test_non_unique_still_refused_without_hint(self):
        self.seed("identical\nidentical")
        with self.assertRaisesRegex(ValueError,"occurs 2 times"):
            self.edit("identical","new")
        self.assertFalse(WRITES)
    def test_success_does_not_add_hint_or_extra_reads(self):
        self.seed("legacy\n")
        reply=self.edit("legacy","new")
        self.assertEqual(STORED["/task/artifact.txt"],b"new\n")
        self.assertNotIn("observed hash",reply.lower())
    def test_unicode_anchor_is_scope_bounded(self):
        self.seed("αβ something\nother\nunique_identifier_世界 actually there\n")
        with self.assertRaises(ValueError) as e:
            self.edit("unique_identifier_世界 isn't here","replacement")
        self.assertIn("line 3",str(e.exception))
        self.assertFalse(WRITES)
if __name__=="__main__":unittest.main(verbosity=2)
