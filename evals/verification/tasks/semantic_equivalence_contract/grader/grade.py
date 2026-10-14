"""Grader for semantics/semantic_equivalence_contract (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed": bool, "score": number, "reasons": [str]}.

Reads <workspace_dir>/out/solution.py and expected.json next to this script. Expected values come from two
sources: fixed cases sealed in expected.json, and a deterministic generated set (seed sealed in expected.json)
whose values are computed here with Python's own ast module, which applies the same precedence and
left-associativity as the spec. Each case runs in a forked child process with an alarm, so a crash or an
infinite loop in one expression cannot affect the others. The child is forked rather than spawned through
the subprocess module because importing subprocess makes the interpreter list every sys.path entry, which
the containment audit would report as a read outside the workspace.
"""

import ast
import hashlib
import json
import os
import random
import signal
import sys
from pathlib import Path

GRADER_DIR = Path(__file__).resolve().parent
SOLUTION_RELATIVE = Path("out") / "solution.py"
CASE_TIMEOUT_S = 10
READ_CHUNK = 65536


def _emit(passed: bool, score: float, reasons: list) -> int:
    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    print(json.dumps({"passed": passed, "score": score, "reasons": unique}, sort_keys=True))
    return 0


def _child_body(solution_dir: Path, expr: str) -> int:
    """Runs in the forked child: evaluate expr and print its type name and repr. Returns exit code."""
    try:
        sys.path.insert(0, str(solution_dir))
        from solution import evaluate

        value = evaluate(expr)
        print(type(value).__name__)
        print(repr(value))
        return 0
    except Exception as exc:  # the child reports any failure through its exit code and output
        print(f"{type(exc).__name__}: {exc}")
        return 1


def _run_child(solution_dir: Path, expr: str) -> tuple[int | None, str]:
    """Return (exit code, combined output); exit code is None when the child hit the alarm."""
    sys.stdout.flush()
    sys.stderr.flush()
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        os.dup2(write_fd, 1)
        os.dup2(write_fd, 2)
        signal.alarm(CASE_TIMEOUT_S)
        code = _child_body(solution_dir, expr)
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    os.close(write_fd)
    chunks = []
    while True:
        data = os.read(read_fd, READ_CHUNK)
        if not data:
            break
        chunks.append(data)
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    output = b"".join(chunks).decode("utf-8", errors="replace")
    if os.WIFSIGNALED(status):
        return (None, output) if os.WTERMSIG(status) == signal.SIGALRM else (1, output)
    return os.WEXITSTATUS(status), output


def _check_case(solution_dir: Path, expr: str, expected: int) -> tuple[str | None, str]:
    """Return (reason_code, detail) for one case; reason_code is None when the case passes."""
    code, output = _run_child(solution_dir, expr)
    if code is None:
        return "expression_evaluation_timeout", f"{expr}: timed out"
    if code != 0:
        last = output.strip().splitlines()[-1:] or [""]
        return "expression_evaluation_error", f"{expr}: {last[0]}"
    lines = output.strip().splitlines()
    if len(lines) != 2 or lines[0] != "int":
        kind = lines[0] if lines else "nothing"
        return "expression_result_mismatch", f"{expr}: expected an int result, got {kind}"
    result = int(lines[1])
    if result != expected:
        return "expression_result_mismatch", f"{expr}: expected {expected}, got {result}"
    return None, ""


def _generate(rng: random.Random, depth: int) -> str:
    """A random expression the grammar admits, with no leading zeros in generated integers."""
    if depth <= 0 or rng.random() < 0.3:
        return str(rng.randint(0, 999))
    roll = rng.random()
    if roll < 0.15:
        return "(" + _generate(rng, depth - 1) + ")"
    left = _generate(rng, depth - 1)
    right = _generate(rng, depth - 1)
    op = rng.choice("+-*")
    return left + op + right


def _ast_value(node: ast.AST) -> int:
    if isinstance(node, ast.Expression):
        return _ast_value(node.body)
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.BinOp):
        left, right = _ast_value(node.left), _ast_value(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
    raise ValueError("unexpected node in generated expression")


def _generated_cases(spec: dict) -> list[tuple[str, int]]:
    rng = random.Random(int(spec["seed"]))
    cases = []
    for _ in range(int(spec["count"])):
        expr = _generate(rng, int(spec["max_depth"]))
        cases.append((expr, _ast_value(ast.parse(expr, mode="eval"))))
    return cases


def _pristine_ok(workspace: Path, expected: dict) -> bool:
    for rel, digest in expected["pristine_sha256"].items():
        try:
            if hashlib.sha256((workspace / rel).read_bytes()).hexdigest() != digest:
                return False
        except OSError:
            return False
    return True


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: grade.py <workspace_dir>", file=sys.stderr)
        return 2
    workspace = Path(sys.argv[1]).resolve()
    spec = json.loads((GRADER_DIR / "expected.json").read_text(encoding="utf-8"))
    cases = [(c["expr"], c["expected"]) for c in spec["fixed_cases"]] + _generated_cases(spec["generated"])
    solution_path = workspace / SOLUTION_RELATIVE
    if not solution_path.is_file():
        return _emit(False, 0.0, ["missing_solution_module"])

    reasons: list[str] = []
    passed_cases = 0
    for expr, expected in cases:
        reason, detail = _check_case(solution_path.parent, expr, expected)
        if reason is None:
            passed_cases += 1
        else:
            reasons.append(reason)
            print(f"[case] {detail}", file=sys.stderr)
    if not _pristine_ok(workspace, spec):
        reasons.append("evidence_file_modified")
    score = passed_cases / len(cases)
    return _emit(not reasons, score, reasons)


if __name__ == "__main__":
    raise SystemExit(main())
