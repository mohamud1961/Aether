"""Delete required outputs: independently incorrect by the declared task contract."""

from .grading import grade
from .sandbox import LocalSandbox


def audit(tasks):
    rows = []
    for task in tasks:
        for output in task.outputs:
            sandbox = LocalSandbox(task, trusted=True)
            try:
                produced = sandbox.exec(
                    'bash "$TASK_ROOT/reference/solve.sh"', task.timeout_s
                )
                before = grade(task, sandbox.root)
                if produced.code or before.error or not before.passed:
                    raise ValueError(f"invalid reference: {task.id}")
                path = (sandbox.root / output).resolve()
                if (
                    not path.is_relative_to(sandbox.root.resolve())
                    or not path.is_file()
                ):
                    raise ValueError(f"missing/unsafe output: {task.id}/{output}")
                path.unlink()
                after = grade(task, sandbox.root)
                rows.append(
                    {
                        "task": task.id,
                        "output": output,
                        "mutation": "delete-required-output",
                        "killed": not after.passed and after.error is None,
                        "grader_error": after.error,
                        "reasons": list(after.reasons),
                    }
                )
            finally:
                sandbox.close()
    return {
        "mutants": len(rows),
        "killed": sum(r["killed"] for r in rows),
        "rows": rows,
    }
