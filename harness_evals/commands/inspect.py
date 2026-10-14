from pathlib import Path


def register(subparsers):
    p = subparsers.add_parser(
        "inspect-export", help="write an Inspect task factory module"
    )
    p.add_argument("tasks", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.set_defaults(func=_run)


def _run(a):
    if a.out.exists():
        raise FileExistsError(a.out)
    source = (
        "from inspect_ai import task\nfrom harness_evals.inspect_export import make_task\n\n@task\ndef harness_tasks():\n    return make_task("
        + repr(str(a.tasks.resolve()))
        + ")\n"
    )
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(source)
    print(
        "wrote Inspect factory; loading/execution require the optional inspect-ai dependency"
    )
    return 0
