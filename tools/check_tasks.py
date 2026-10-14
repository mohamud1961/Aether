#!/usr/bin/env python3
"""Solvability + careless-agent gate for task dirs.

For each task: (1) solvability: run reference/solve.sh in a copy of workspace/ with no TASK_ROOT and
no access to grader/ (task copied without grader/, ceiling.md, known_bad/, careless/); grade must pass.
(2) each careless/*.sh run the same way must FAIL; if its header has '# expect: <code>', that code
must appear in the grader's reasons. Exit 1 on any violation.
Usage: check_tasks.py <tasks_root>
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

def grade(task, ws):
    out = subprocess.run([sys.executable, str(task / "grader" / "grade.py"), str(ws)],
                         capture_output=True, text=True, timeout=300)
    return json.loads(out.stdout.strip().splitlines()[-1])

def run_script(task, script):
    tmp = Path(tempfile.mkdtemp())
    ws = tmp / "ws"; shutil.copytree(task / "workspace", ws)
    # visible copy: prompt only (no grader, reference answers, known-bads)
    vis = tmp / "task"; vis.mkdir(); shutil.copy(task / "prompt.md", vis / "prompt.md")
    env = {k: v for k, v in os.environ.items() if k != "TASK_ROOT"}
    env["PROMPT_PATH"] = str(vis / "prompt.md")
    r = subprocess.run(["bash", str(script)], cwd=ws, env=env, capture_output=True, text=True, timeout=300)
    return ws, r

def expect(script):
    for line in script.read_text().splitlines()[:5]:
        if line.startswith("# expect:"):
            return line.split(":", 1)[1].strip()
    return None

def main(root):
    bad = 0
    for task in sorted(p.parent.resolve() for p in Path(root).rglob("task.yaml")):
        ws, r = run_script(task, task / "reference" / "solve.sh")
        g = grade(task, ws)
        solv = "ok" if g["passed"] else f"FAIL {g['reasons'][:3]} rc={r.returncode} {r.stderr.strip()[:120]}"
        bad += solv != "ok"
        cl = sorted((task / "careless").glob("*.sh")) if (task / "careless").is_dir() else []
        res = []
        for c in cl:
            ws2, _ = run_script(task, c); g2 = grade(task, ws2); e = expect(c)
            ok = (not g2["passed"]) and (e is None or e in g2["reasons"])
            bad += not ok
            res.append(f"{c.stem}:{'ok' if ok else 'PASSED-OR-WRONG-REASON ' + str(g2['reasons'][:3])}")
        print(f"{task.name:40} solvable={solv}  careless={len(cl)} {' '.join(r for r in res if 'ok' not in r[-3:])}")
    print("VIOLATIONS", bad); return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
