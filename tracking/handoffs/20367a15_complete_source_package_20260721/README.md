# Exact-source package and local certification gate

Status: local package gate passed; VM certification not yet run.

## Authority

- Production commit: `20367a15b919cc82dae0adcc17ef1826874f3773`
- Production tree: `f32652cf58195ba74a3061f7f5b10a126d67ae28`
- Package construction: complete `git archive` of the tracked commit tree
- Tracked entries: 7,989 (7,988 blobs and one recorded gitlink)
- Package archive SHA-256: `b2bf351f6f95262cd409c5da246de35a5e5ac3c6ab4ccef238c7a3fb7245beb7`
- Package manifest SHA-256: `b0dc9bfa6e7cbdd56bb931173837287fc02d1717ae56d42e868c93a5654acb40`

The archive itself is not committed because it is 305 MiB and is reproducibly
generated from the production commit. The full file/hash manifest and builder
are committed.

## Completeness and credential audit

- Missing archive paths: 0
- Unexpected archive paths: 0
- File/hash mismatches: 0
- Tracked macOS sidecars or bytecode: 0
- Tracked credential-path candidates: 0
- Azure/OpenAI credential-assignment candidates: 0
- Private-key-like committed fixture/trace candidates: 36

The 36 disclosed private-key-like records are under historical
`openssl-selfsigned-cert` fixtures and traces. They are committed synthetic
task artifacts, not live Azure/OpenAI runtime credentials. Runtime environment
files and untracked credentials are excluded by Git-tree construction.

## Local extracted-package certification

The authoritative unrestricted run passed all 17 required cases.

- Aggregate SHA-256: `38a34f6006ef69da39073f84109958b69a653122656ccd670319b024ed6cdbc8`
- Final marker SHA-256: `dbc466354e9a0c7c6c1395294362acb5c38c8025a1326df65b9f327a3740abfe`
- Final marker status: `finalized`

An initial sandboxed attempt was invalid due to three localhost socket-bind
`PermissionError` failures; 653 tests passed. The same package passed outside
that sandbox restriction. This is classified as an environment invalid, not a
source failure.

Certification intentionally emitted two ignored deterministic-integration
artifact directories inside the extracted source. They were retained in the
certification evidence archive, moved outside the source, and the complete
source manifest was rechecked. Final state: 7,988 files verified, zero missing,
zero unexpected, and zero mismatches.

## Evidence hashes

- `source-package-receipt.json`: `eef3a9ab6072e61bf31f56db3db8d99babfb47e4bb7f6ac6622ed33045b195c1`
- `post-certification-before-quarantine.json`: `687ac5f64d100e66167be2994470b9b6e8da83c712e69fc983933e4d5b804b63`
- `post-certification-clean.json`: `e354c973252cc2c24dd7aeeebb3582dbc35a92d701fed84a03809bfafed622c1`
- `local-certification-evidence.tar.gz`: `a98ca942507194e5eaae25ef5558a8444cf46faca92b8813930ba37b6344c0c0`

## Review disposition

`codex review --uncommitted` could not initialize because the Codex state DB
was read-only. Manual adversarial review found and repaired four real issues:
gitlink handling, directory-symlink inventory, link extraction confinement,
and mode verification. The builder's known-bad attempts also failed closed on
an omitted gitlink-adjacent path and post-run source additions.

The committed private-key-like fixture records are consciously accepted as
non-operational historical evidence. No provider credential candidates were
accepted.

## Next gate

Transfer the exact archive plus manifest to the Azure VM, verify archive and
every extracted file hash, then run one serial authoritative 17-case Linux
certification. Do not launch role boards unless that run is 17/17 with a sealed
marker and clean manifest state.
