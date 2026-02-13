import re
from typing import Optional, Tuple

class PatternLibrary:
    """Strict, anchored regex patterns for missing dependency detection."""

    # Python Patterns
    # Matches: ModuleNotFoundError: No module named 'foo'
    # Guard: Must capture exact module name
    PYTHON_MODULE_NOT_FOUND = re.compile(
        r"^ModuleNotFoundError: No module named '(?P<name>[A-Za-z0-9_]+)'$"
    )
    # Matches: ImportError: No module named foo
    PYTHON_IMPORT_ERROR = re.compile(
        r"^ImportError: No module named (?P<name>[A-Za-z0-9_]+)$"
    )

    # Node Patterns
    # Matches: Cannot find module 'foo' (standard node error)
    NODE_MODULE_NOT_FOUND = re.compile(
        r"^Cannot find module '(?P<name>[^']+)'$"
    )
    # Matches: Error: Cannot find module 'foo' (wrapped error)
    NODE_ERROR_MODULE_NOT_FOUND = re.compile(
        r"^Error: Cannot find module '(?P<name>[^']+)'$"
    )

    # Shell Patterns
    # Matches: foo: command not found (bash/zsh)
    # Guard: Captures possible binary name, caller must validate against argv[0]
    CMD_NOT_FOUND_PREFIX = re.compile(
        r"^(?P<name>\S+): command not found$"
    )
    # Matches: command not found: foo (zsh variant)
    CMD_NOT_FOUND_SUFFIX = re.compile(
        r"^command not found: (?P<name>\S+)$"
    )

    # System Patterns (Fail Closed)
    # Matches bad C/C++ includes
    C_HEADER_MISSING = re.compile(
        r"^fatal error: (?P<header>\S+\.h): No such file or directory$"
    )
    # Matches linker errors
    LINKER_LIB_MISSING = re.compile(
        r"^ld: library not found for -l(?P<name>\S+)$"
    )

    @staticmethod
    def match_python_missing(stderr_line: str) -> Optional[str]:
        """Returns module name if strictly matched, else None."""
        m = PatternLibrary.PYTHON_MODULE_NOT_FOUND.match(stderr_line)
        if m:
            return m.group("name")
        m = PatternLibrary.PYTHON_IMPORT_ERROR.match(stderr_line)
        if m:
            return m.group("name")
        return None

    @staticmethod
    def match_node_missing(stderr_line: str) -> Optional[str]:
        """Returns package name if strictly matched, else None."""
        m = PatternLibrary.NODE_MODULE_NOT_FOUND.match(stderr_line)
        if m:
            return m.group("name")
        m = PatternLibrary.NODE_ERROR_MODULE_NOT_FOUND.match(stderr_line)
        if m:
            return m.group("name")
        return None

    @staticmethod
    def match_binary_missing(stderr_line: str) -> Optional[str]:
        """Returns binary name if strictly matched, else None."""
        m = PatternLibrary.CMD_NOT_FOUND_PREFIX.match(stderr_line)
        if m:
            return m.group("name")
        m = PatternLibrary.CMD_NOT_FOUND_SUFFIX.match(stderr_line)
        if m:
            return m.group("name")
        return None

    @staticmethod
    def match_system_missing(stderr_line: str) -> Optional[str]:
        """Returns missing component (header or lib) if strictly matched."""
        m = PatternLibrary.C_HEADER_MISSING.match(stderr_line)
        if m:
            return m.group("header")
        m = PatternLibrary.LINKER_LIB_MISSING.match(stderr_line)
        if m:
            return m.group("name")
        return None
