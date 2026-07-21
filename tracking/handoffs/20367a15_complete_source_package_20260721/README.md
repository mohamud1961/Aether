# Exact-source package, VM certification, and role-board gate

Status: exact package and local/VM deterministic certification passed; Solver
and Verifier role boards finalized but are non-promotable.

## Authority

- Production commit: `20367a15b919cc82dae0adcc17ef1826874f3773`
- Production tree: `f32652cf58195ba74a3061f7f5b10a126d67ae28`
- Package construction: complete `git archive` of the tracked commit tree
- Tracked entries: 7,989 (7,988 blobs and one recorded gitlink)
- Package archive SHA-256: `b2bf351f6f95262cd409c5da246de35a5e5ac3c6ab4ccef238c7a3fb7245beb7`
- Package manifest SHA-256: `1ac7efe9241cc635d6fcffb1a3653ae10ea5b373090ae470a0ffea50155d596e`

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

## Local and VM extracted-package certification

The corrected v6 package passed all 17 required cases locally and on the fresh
Linux VM. The v6 manifest uses Git executable-bit semantics so harmless
owner/group write-mask differences between macOS and Linux cannot create false
source mismatches.

- Local aggregate SHA-256: `f80cab328d9e578b4a7f62e3f02ce2779b99c39c923e470459a40375348981f7`
- Local final marker SHA-256: `aac6e9df472fe0472a6b380e2ee13872ccab87019183070aa419e3c0354f1b6d`
- VM aggregate SHA-256: `ebb768d94dbdaaa4a804c32cce378f82ed3b859990563b64ab93d0e8695f5e41`
- VM final marker SHA-256: `20accefa66fe8a9e3afb085acac7405dee2ed56354f8ad70f7b9e8e11cd96080`
- Both final marker statuses: `finalized`

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

- `source-package-manifest-v6.json`: `1ac7efe9241cc635d6fcffb1a3653ae10ea5b373090ae470a0ffea50155d596e`
- `source-package-receipt-v6.json`: `9d3857c0e14a571896534d043cb13367a690d60ab3e0cbff82f1cbfee83ca17b`
- `local-certification-v6-evidence.tar.gz`: `4ab346071486041d81bd6e9715533ddf184412d33d5bce3594e4a1c8fa52c702`
- `vm-certification-v6-evidence.tar.gz`: `886505915fc71f01e6b96c383c73b7aa7e76452d3f05e4bee71bf75b7edab687`
- `role-boards/solver-role-board-d593452472b0b49a.tar.gz`: `a52b38366a458e7df8800f8a8875cc3941d219c23ad5f1515c67daa6e9064901`
- `role-boards/verifier-role-board-ae2ea6a3be904a99.tar.gz`: `90a517e1db7657c8286a95a2491acf12136018bf1534d89d305919c5a62b9e38`

The earlier v5 artifacts below are preserved as historical evidence of the
pre-portability package attempt.

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

## Role-board result and next gate

See `ROLE_BOARD_CLASSIFICATION.md` for the full 24-row Solver diagnostic and
five-row Verifier classification. Solver was dominated by an Azure JSON-mode
request-contract defect (18 request-time 400s); only four rows were scorable
and all four chose the expected action. Verifier caught all three known-bad
states but rejected both known-good states, one semantically and one as a
provider-invalid row. Both boards finalized fail closed, but neither promotes.

Do not launch Architect, perception, smoke, or official boards. The next goal
must repair and test the generic JSON-mode request contract, rerun the unchanged
Solver board, and diagnose the two Verifier known-good failures without
weakening the verifier contract.
