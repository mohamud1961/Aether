# Aether-Next Legacy Path Removal Inventory v1

Status: classification in progress; no path below is production authority merely
because it exists in the repository.

| Surface | Current role | Target decision |
|---|---|---|
| `aether_next/kernel.py` production loop | production | retain as sole kernel; reduce after invariant migration |
| `aether_next/runtime.py` | compatibility/runtime bridge | audit callers; remove any duplicate execution/completion ownership |
| `aether_next/run_adapter.py` | adapter | retain only canonical Workbench/Docker entry functions |
| `aether_next/reference_legacy/` | historical reference | quarantine outside production imports or remove after migration evidence |
| `aether_next_build/reference_legacy/` | historical reference | same; never import from production |
| replay engines/runners | evaluation substrate | retain only when they invoke production code; remove parallel simulation logic |
| many `run_*eval.py` scripts | historical/eval launchers | consolidate after scorecard certification |
| archived boards/traces/snapshots | evidence | move out of source package or clearly classify as immutable evidence |
| `task_capability.py` keyword strategy classifier | trusted model-facing inference | remove from model-facing production path; replace with factual file/tool metadata |
| Workbench `tool_policy` | legacy Architect selection | remove from canonical IR/parser/compiler and prompts |
| legacy RuntimeConfigIR selected capabilities | legacy configuration | prevent Architect authority over fixed tool surface; simplify after migration |
| model-output first-object extraction helpers | protocol compatibility | remove from canonical provider/Solver path; strict single object only |
| multiple proof/evidence representations | mixed | consolidate into canonical inspection registry plus clause proof references |
| V5-ported tests expecting old API | migration tests | either port to production API or archive; collection failure cannot remain |
| task/run-specific Gold runners | board evidence | do not use as production architecture; archive after extracting generic tests |
| alternate process registries | mixed | converge on one real identity/generation registry |
| alternate completion helpers | mixed | ensure `_completed_result` is reachable only through one ready conjunction |

## Removal gate

Before deleting a path:

1. identify all callers;
2. classify any unique invariant it tests or implements;
3. port the invariant to the canonical production path;
4. add production-bound tests;
5. remove imports and dead configuration;
6. verify source manifest and full declared suites.

The aim is one authoritative path, not deletion for line-count aesthetics.
