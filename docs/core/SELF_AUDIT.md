# Full engineering self-audit — 13 October 2026

Entry: 32432e560. User requires engineering completion and self-audit, with no GLM calls,
no subagents and no browser. Review claims against the declared one-shot Harbor/Linux envelope.
The matched GLM comparison is excluded by the principal's latest explicit instruction.

## Reproduction queue (before repairs)

| ID | Observable failure / owning module | Proof through an interface | Acceptance |
|---|---|---|---|
| A1 | Startup or end-trace failure bypasses cleanup / loop | Inject startup failure after real REPL launch; inject end-record error | Each owned closer runs independently; original failure and cleanup failures retained |
| A2 | Upload or exec can overrun total deadline / loop, env | A blocked transfer inside a real loop, with a subsecond outer diagnostic bound | Run returns timeout within its work budget; cleanup has a separate bounded reserve |
| A3 | Missing usage becomes zero in Harbor summary; missing criterion remains pass / accounting, review | Script a response without usage and inspect saved record; omit an asked criterion | Unknown top-level totals are null; review cannot be labeled clean |
| A4 | Provider stream resources remain open; early EOF can be treated as success / provider | Real async stream fixture with close receipt and fragmented calls; abrupt EOF | Close attempted on success/failure/cancel; incomplete stream has no side effects |
| A5 | Long-line file clipping has no usable continuation; blank lines can be classified binary; whitespace paths change / files | Real long UTF-8 file paged to its tail, blank file, path with edge spaces | Bounded page with explicit continuation; valid paths/content honored |
| A6 | Interrupted write can damage original; chmod failure hidden / files, env | Interrupt a real partial upload; inject failed mode preservation | Atomic replacement; failed commit preserves original bytes and mode |
| A7 | Custom CLM paths and indirect terminal edits are not faithfully read back / context, loop | Edit configured mirror via shell variable rather than a literal LIVE_CTX argument | Published path matches config; edit observed; original history recoverable |
| A8 | Clone host timeouts/creation errors do not consistently remove owned resources / clone | Fault-injected host interface plus real Linux clone cleanup controls | Cleanup named resources on each error; record unresolved host cleanup honestly |
| A9 | Direct Docker proof does not qualify full Harbor adapter / Harbor | Installed wheel, actual Harbor environment/class, local scripted HTTP endpoint, native grader | Exact adapter/provider wire path runs with real tool effects and independent grade, zero provider spend |
| A10 | Standalone package has no current whole-tree validation/lint artifact / package | Isolated final wheel install and full portable suite, Linux/Harbor gate | Fresh source and wheel custody, explicit platform coverage, clean portable folder |

## Evidence rules

Tests exercise real shell/file/Docker behavior. Scripted providers are explicitly fixtures; they establish
engineering fidelity and do not establish GLM task-solving improvement. Known-bad controls must fail before
repair. Every finding will be accepted/repaired or rejected with a concrete reason. No new live provider,
production activation, merge, release or protected-task access is authorized by this audit.
