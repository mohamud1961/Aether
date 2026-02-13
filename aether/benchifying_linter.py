"""
Anti-Benchifying Linter

Static analysis linter that scans policy, trigger, and detector files for forbidden
patterns that would constitute task-identity routing (benchifying).

Doctrine v1.3 §5.2 Forbidden in Triggers:
- task_name == "repair-history"  (Task-name routing)
- task_category == "security"  (Category-based heuristics)
- if "maze" in task_description  (Benchmark-specific parsing)
- known_hard_tasks.contains(task)  (Hardcoded task lists)
- task_id in special_handling  (Task-identity routing)
"""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional


__all__ = ["BenchifyingLinter", "LinterViolation"]


class LinterViolation:
    """A single linter violation."""
    
    def __init__(
        self,
        file: str,
        line: int,
        pattern: str,
        content: str,
        violation_type: str,
    ):
        self.file = file
        self.line = line
        self.pattern = pattern
        self.content = content
        self.violation_type = violation_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "pattern": self.pattern,
            "content": self.content,
            "type": self.violation_type,
        }


class BenchifyingLinter:
    """Static analysis linter for anti-benchifying enforcement."""

    # Forbidden identifier patterns (task identity)
    FORBIDDEN_IDENTIFIERS = [
        r'\btask_name\b',
        r'\btask_id\b',
        r'\btask_category\b',
        r'\btask_description\b',
        r'\bvariant_id\b',
        r'\bvariant_of\b',
        r'\bdifficulty\b',
        r'\bdataset_name\b',
    ]

    # Forbidden string literal patterns (hardcoded task names/lists)
    FORBIDDEN_LITERALS = [
        # Known TBench task names (non-exhaustive, pattern-based)
        r'"repair-history"',
        r"'repair-history'",
        r'"train-text-classifier"',
        r"'train-text-classifier'",
        r'"tiny-model-golf"',
        r"'tiny-model-golf'",
        r'"dual-language-build"',
        r"'dual-language-build'",
        r'"render-scene"',
        r"'render-scene'",
        r'"maze"',
        r"'maze'",
        # Category-based routing
        r'"security"',
        r"'security'",
        r'"crypto"',
        r"'crypto'",
        # Hardcoded list patterns
        r'HARD_TASKS\s*=',
        r'EASY_TASKS\s*=',
        r'SPECIAL_TASKS\s*=',
        r'KNOWN_TASKS\s*=',
    ]

    # Files to scan (relative to harness root)
    SCAN_PATTERNS = [
        '*policy*.py',
        '*trigger*.py',
        '*detector*.py',
        'control_plane.py',
        'governance_gate.py',
    ]

    # Allowlist: these patterns are okay even if they match
    ALLOWLIST = [
        r'# ALLOWED:',  # Explicit exemption comment
        r'def test_',   # Test code can reference forbidden patterns
        r'""".*"""',    # Docstrings are informational
    ]

    def __init__(self, harness_root: Path):
        self.harness_root = harness_root
        self.violations: List[LinterViolation] = []

    def scan_file(self, filepath: Path) -> List[LinterViolation]:
        """Scan a single file for benchifying violations."""
        violations = []
        try:
            content = filepath.read_text()
            lines = content.split('\n')
        except Exception as e:
            violations.append(LinterViolation(
                file=str(filepath),
                line=0,
                pattern=f'READ_ERROR: {e}',
                content='',
                violation_type='ERROR',
            ))
            return violations

        for i, line in enumerate(lines, 1):
            # Skip allowlisted lines
            if any(re.search(pat, line) for pat in self.ALLOWLIST):
                continue

            # Check forbidden identifiers
            for pattern in self.FORBIDDEN_IDENTIFIERS:
                if re.search(pattern, line):
                    violations.append(LinterViolation(
                        file=str(filepath),
                        line=i,
                        pattern=pattern,
                        content=line.strip()[:80],
                        violation_type='FORBIDDEN_IDENTIFIER',
                    ))

            # Check forbidden literals
            for pattern in self.FORBIDDEN_LITERALS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(LinterViolation(
                        file=str(filepath),
                        line=i,
                        pattern=pattern,
                        content=line.strip()[:80],
                        violation_type='FORBIDDEN_LITERAL',
                    ))

        return violations

    def scan_all(self) -> List[LinterViolation]:
        """Scan all relevant files in the harness."""
        self.violations = []

        if not self.harness_root.exists():
            self.violations.append(LinterViolation(
                file=str(self.harness_root),
                line=0,
                pattern='',
                content=f'harness root not found: {self.harness_root}',
                violation_type='ERROR',
            ))
            return self.violations

        for pattern in self.SCAN_PATTERNS:
            for filepath in self.harness_root.glob(pattern):
                if filepath.is_file():
                    file_violations = self.scan_file(filepath)
                    self.violations.extend(file_violations)

        return self.violations

    def format_report(self) -> str:
        """Format violations as a human-readable report."""
        if not self.violations:
            return "✅ No benchifying violations found."

        lines = [f"🔴 Found {len(self.violations)} benchifying violation(s):\n"]
        for v in self.violations:
            if v.violation_type == 'ERROR':
                lines.append(f"  ERROR: {v.content}")
            else:
                lines.append(f"  {v.file}:{v.line} [{v.violation_type}]")
                lines.append(f"    Pattern: {v.pattern}")
                lines.append(f"    Content: {v.content}")
                lines.append("")
        return '\n'.join(lines)

    def has_violations(self) -> bool:
        """Return True if any violations were found."""
        return len(self.violations) > 0
