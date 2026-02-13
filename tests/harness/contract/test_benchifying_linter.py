"""
Anti-hardcoding Linter (Layer 1)

Contract test that scans policy, trigger, and detector files for forbidden patterns
that would constitute task-identity routing (hardcoding).

Doctrine v1.3 §5.2 Forbidden in Triggers:
- task_name == "repair-history"  (Task-name routing)
- task_category == "security"  (Category-based heuristics)
- if "maze" in task_description  (evaluation suite-specific parsing)
- known_hard_tasks.contains(task)  (Hardcoded task lists)
- task_id in special_handling  (Task-identity routing)
"""

import os
import re
import tempfile
import unittest
from pathlib import Path

# Import from production module
from aether.hardcoding_linter import hardcodingLinter


class TesthardcodingLinter(unittest.TestCase):
    """Contract tests for anti-hardcoding linter."""

    @classmethod
    def setUpClass(cls):
        # Find the harness root
        tests_dir = Path(__file__).parent.parent.parent.parent
        cls.harness_root = tests_dir / 'aether'

    def test_no_hardcoding_violations_in_harness(self):
        """Contract: No task-identity routing in policy/trigger/detector files."""
        linter = hardcodingLinter(self.harness_root)
        violations = linter.scan_all()

        if violations:
            self.fail(linter.format_report())

    def test_linter_detects_task_name_routing(self):
        """Linter correctly identifies task_name comparisons."""
        linter = hardcodingLinter(Path('/nonexistent'))

        # Create temp content for testing
        test_content = '''
def bad_policy(task_name, state):
    if task_name == "repair-history":
        return special_handling()
'''
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_content)
            f.flush()
            violations = linter.scan_file(Path(f.name))
            os.unlink(f.name)

        self.assertGreater(len(violations), 0)
        patterns_found = [v.pattern for v in violations]
        self.assertTrue(any('task_name' in p for p in patterns_found))

    def test_linter_ignores_allowlisted_patterns(self):
        """Linter skips lines with # ALLOWED: comment."""
        linter = hardcodingLinter(Path('/nonexistent'))

        test_content = '''
# ALLOWED: this is for testing only
if task_name == "repair-history":
    pass
'''
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_content)
            f.flush()
            violations = linter.scan_file(Path(f.name))
            os.unlink(f.name)

        # The allowlisted line should be skipped
        non_allowlisted = [v for v in violations if 'ALLOWED:' not in v.content]
        # Second line is NOT allowlisted and should still be caught
        self.assertGreater(len(non_allowlisted), 0)

    def test_linter_detects_hardcoded_task_lists(self):
        """Linter catches HARD_TASKS = [...] patterns."""
        linter = hardcodingLinter(Path('/nonexistent'))

        test_content = '''
HARD_TASKS = ["tiny-model-golf", "dual-language-build"]
'''
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_content)
            f.flush()
            violations = linter.scan_file(Path(f.name))
            os.unlink(f.name)

        self.assertGreater(len(violations), 0)
        self.assertTrue(any('HARD_TASKS' in v.pattern for v in violations))


if __name__ == '__main__':
    unittest.main()
