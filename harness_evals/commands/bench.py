import json
from pathlib import Path

from harness_evals import mutation, registry, tournament, verifier_bench
from harness_evals.task import discover


def register(subparsers):
    p = subparsers.add_parser("mutate", help="audit required-output deletion mutants")
    p.add_argument("tasks", type=Path)
    p.set_defaults(func=lambda a: _print(mutation.audit(discover(a.tasks))))
    p = subparsers.add_parser(
        "verifier-cases", help="build labelled reference/known-bad states"
    )
    p.add_argument("tasks", type=Path)
    p.add_argument("out", type=Path)
    p.set_defaults(
        func=lambda a: _print(verifier_bench.build_cases(discover(a.tasks), a.out))
    )
    p = subparsers.add_parser(
        "verifier-bench", help="compare a command verifier with/without claims"
    )
    p.add_argument("cases", type=Path)
    p.add_argument("--command", required=True)
    p.set_defaults(func=lambda a: _print(verifier_bench.evaluate(a.cases, a.command)))
    p = subparsers.add_parser("registry", help="render historical comparisons")
    p.add_argument("records", type=Path)
    p.set_defaults(func=lambda a: _text(registry.render(a.records)))
    p = subparsers.add_parser(
        "lift", aliases=["tournament"], help="run a sealed paired study"
    )
    p.add_argument("plan", type=Path)
    p.add_argument("--seal", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-rows", required=True, type=int)
    p.add_argument("--sandbox", choices=["local", "docker"], default="docker")
    p.set_defaults(
        func=lambda a: _text(
            tournament.run(a.plan, a.seal, a.out, a.max_rows, a.sandbox)
        )
    )


def _print(value):
    print(json.dumps(value, indent=2))
    return 0


def _text(value):
    print(value)
    return 0
