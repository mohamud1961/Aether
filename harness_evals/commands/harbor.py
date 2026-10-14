from pathlib import Path

from harness_evals.harbor_ingest import ingest


def register(subparsers):
    p = subparsers.add_parser(
        "harbor-ingest", help="import real single-step Harbor trial results"
    )
    p.add_argument("results", nargs="+", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument("--arm", required=True)
    p.set_defaults(func=_run)


def _run(a):
    rows = ingest(a.results, a.out, a.run_id, a.arm)
    print(f"imported {len(rows)} rows; unavailable fields flagged in trace sidecar")
    return 0
