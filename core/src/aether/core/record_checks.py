"""Which terminal commands are checks, what a check printed as results, and the Check record itself.

Split from record.py (module-size cap, 2026-10-26) with the code unchanged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_EXEC = {
    "python", "python3", "pytest", "py.test", "bash", "sh", "node", "deno", "bun", "make", "cargo", "go", "gcc",
    "g++", "cc", "c++", "clang", "clang++", "java", "javac", "rustc", "ruby", "perl", "rscript", "julia", "ocaml",
    "dune", "npm", "npx", "yarn", "pnpm", "uv", "poetry", "tox", "ctest", "diff", "cmp", "ghc", "coqc", "php",
    "lua", "swift", "dotnet", "mvn", "gradle", "sqlite3", "psql", "gdb", "valgrind", "tsc", "tsx", "ts-node",
}
_PREFIX = {"sudo", "time", "nice", "env", "nohup", "stdbuf", "exec", "command"}
_NOT_RUN = re.compile(r"(-m pip\b|\bpip3? |\buv (pip|add|venv|sync)|\bnpm (i|install|ci)\b|\bapt(-get)? )")
RESULT_LINES = 3
_FOOTER = re.compile(r"\n?\[(exit \d+|still running)[^\n]*\]\s*$")


def is_check(command: str) -> bool:
    """True when some segment of the command runs code: an interpreter, test runner, compiler, ./x, diff or cmp."""
    if _NOT_RUN.search(command) or re.search(r"&\s*$", command.strip()):
        return False
    for seg in re.split(r"&&|\|\||;|\n|\|", command):
        words = seg.strip().split()
        while words and ("=" in words[0] and not words[0].startswith(("=", "./", "/")) or words[0] in _PREFIX):
            words = words[1:]
        if words and words[0] == "timeout":
            words = [w for w in words[1:] if not w.startswith("-")][1:]
        if not words:
            continue
        first = words[0]
        if first.startswith("./") or first.split("/")[-1].lower().rstrip("0123456789.") in _EXEC:
            return True
    return False


def results(out: str) -> list[str]:
    """The printed lines that carry numbers or a verdict word: what a check reports, in order, without duplicates."""
    seen: list[str] = []
    for line in _FOOTER.sub("", out).splitlines():
        line = " ".join(line.split())
        if line and len(line) <= 300 and line not in seen and re.search(r"\d|\b(pass|fail|ok|error|true|false|mismatch|"
                                                                        r"match|differ|wrong|correct)", line, re.I):
            seen.append(line)
    return seen


# run-to-run noise, never a result: shell `time`, process ids, wall-clock durations, timestamps, addresses
_NOISE = re.compile(r"^(real|user|sys)\s|\bpid\b|\belapsed\b|\btook\b|\d(\.\d+)?\s*(ms|s|sec|secs|seconds)\b|"
                    r"\d\d:\d\d:\d\d|0x[0-9a-f]{6,}", re.I)


def differing(a: str, b: str) -> tuple[list[str], list[str]]:
    """The result lines only in ``a`` and only in ``b``, the last ones (where checks print verdicts), noise dropped."""
    ra = [x for x in results(a) if not _NOISE.search(x)]
    rb = [x for x in results(b) if not _NOISE.search(x)]
    return [x for x in ra if x not in rb][-RESULT_LINES:], [x for x in rb if x not in ra][-RESULT_LINES:]


def norm(command: str) -> str:
    return " ".join(command.split())


def short(command: str, limit: int = 160) -> str:
    one = norm(command)
    return one if len(one) <= limit else one[: limit - 3] + "..."


@dataclass
class Check:
    seq: int
    t: float
    command: str
    exit: int
    elapsed: float
    cwd: str
    files: dict[str, str] = field(default_factory=dict)  # relative path -> sha256 when it finished
    out: str = ""  # tail of what it printed (measure)

    @property
    def passed(self) -> bool:
        return self.exit == 0

    @property
    def failed(self) -> bool:  # an exit status of the command itself, not a signal (interrupt, kill, timeout)
        return 0 < self.exit < 124
