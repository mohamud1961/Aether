# V5 reference corpus — archived compatibility evidence

This directory preserves the deterministic test sources shipped in
`AETHER_NEXT_EXECUTED_UPGRADE_V5_20260711.zip` as historical evidence. The old
V5 production package/API topology is superseded and is **not** a production
runtime contract.

The 23 historical test modules and their conftest are retained byte-for-byte as
`reference_test_*.py` and `reference_conftest.py`. The `reference_` prefix is
intentional: pytest must not execute this obsolete compatibility harness as part
of current qualification, and Aether must not resurrect obsolete APIs such as
`ProcessRegistry`, `EvidenceRecord`, or the old config compiler merely to make
historical imports work.

`V5_PORT_MANIFEST.md` records the original source/API boundary.
`V5_REPLACEMENT_COVERAGE_V1.json` binds every archived module to maintained
current-production test nodes that preserve the retained behavioral intent. The
active gate `../test_v5_ported_replacement_coverage_v1.py` verifies historical
byte custody, complete module assignment, and current replacement-node custody.
Final deterministic qualification additionally requires those replacement nodes
to pass normally; a skip or failure cannot be hidden by the archive disposition.

The current policy is therefore:

- preserve historical V5 bytes exactly;
- keep the obsolete V5 runtime/package absent;
- expose no collectable `test_*.py` or active `conftest.py` in this archive;
- qualify retained behavior on maintained canonical `aether_next` tests;
- fail closed if an archived source changes, a module loses replacement coverage,
  or a required replacement node does not pass.
