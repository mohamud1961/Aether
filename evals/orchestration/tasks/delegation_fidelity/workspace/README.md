# OPS-4471 working folder

- `thread/request_thread.md`: the request thread for this refresh.
- `specs/`: packet schema and merge rules the lead works from.
- `workers/results/`: results the three workers reported back.
- `data/`: the frozen ledger snapshot used by reconcile.
- `vendor/`: owned by the vendor sync job. Do not edit.

Worker packets have these fields: `packet_version`, `worker`, `goal`, `deadline`, `constraints`,
`outputs`. (Older template, kept for reference.)
