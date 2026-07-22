# Causal Verifier Targeted v1: forensic diagnosis

## Authority surface

- Source: `6e5697f942fda05fbffeb349d4c8c21cc039ef73`, tree `c5acd62e024d7233d36c5417c4e5a81eaf5915ab`.
- Evaluation evidence: `/private/tmp/aether-causal-verifier-targeted-v1-6e5697f9/`.
- Scoreable log rows: 3. Provider-invalid image row: 1, excluded from model-quality scoring.
- Missing evidence: the evaluator preserves each inspection request/result and final raw verifier response, but not the raw verifier text for intermediate turns or the exact full message list sent on every provider call. Earlier-turn beliefs are therefore inferred from the immutable requests, results, static prompt, and provider metadata.

## Findings

### Sample 1 — valid, incomplete measurement

Observed sequence: the runtime auto-read `summary.csv`, then the model listed log filenames. It did not inspect representative raw line content or execute a recomputation. After the overlay directory listing, it did not supply the required `method_validity` record; the runtime returned `uncertain_missing_evidence`.

Classification: `verifier_prompt` / `completion_semantics`, confidence medium. The cautious decision not to invent a parser is consistent with the evidence available. It also shows the current round allocation can spend useful capacity before discovery, execution, and synthesis all occur.

### Sample 2 — correct verdict, unsafe method

Observed sequence: before any raw inspection result, the model cited `task:prompt` and ran one command that read raw files, displayed boundary lines, recomputed totals, and compared the CSV. The command used `re.compile(r'\\b(ERROR|WARNING|INFO)\\b').search(line)`. Its later result was completed and reported a `method_validity` record saying it counted exact severity tokens.

Classification: `evidence_acquisition` with `proxy_target_success`, confidence high. The command's numerical agreement is not evidence that the whole-line parser selected the authoritative field. The model saw a prompt and charter that require exact severities and raw-log inspection, but neither made observation a mandatory prerequisite to authoring a method. A one-command route was permitted and a matching output offered a strong completion affordance.

### Sample 3 — grounded successful control

Observed sequence: it listed the workspace, then read the CSV and representative boundary logs, then cited those prior inspection IDs and executed a command using `re.compile(r'\\[(ERROR|WARNING|INFO)\\]')`. It completed with a method-validity record connected to the executed command.

Classification: robust within this one trace, confidence medium. It is consistent with the observation-order hypothesis; one sample does not prove the mechanism generally.

### Image sentinel — unmeasured

The text and visual observations succeeded. The next verifier provider call returned multiple distinct assistant outputs, which was quarantined. Classification: `provider_failure`; no model-quality conclusion.

## Comparison lens for the observation-first ablation

This table is the fixed read-only lens for interpreting the next three log
samples. `Observed` means preserved request/result or command evidence;
`inferred` means a constrained explanation from that evidence. It does not
claim access to unretained intermediate model text.

| Stage | Sample 1 | Sample 2 | Sample 3 |
| --- | --- | --- | --- |
| Initial facts visible | `summary.csv` auto-read; task categories. Observed. | `summary.csv` auto-read; task categories. Observed. | `summary.csv` auto-read; task categories. Observed. |
| Important representation unknown | Raw line grammar and whether category words occur outside the authoritative field. Observed as uninspected. | Same unknown. Observed as uninspected before the combined command. | Same unknown before its first raw-line read. Observed. |
| First material inspection | Listed available logs. Observed. | Combined file discovery, raw-line display, recomputation, and comparison. Observed. | Listed workspace, then read CSV and representative raw lines. Observed. |
| Method commitment point | No executable parser submitted. Observed. | Whole-line token-search parser authored before raw-line observations were returned. Observed. | Bracket-field parser authored after cited raw-line observations. Observed. |
| Why evidence appeared sufficient | No sufficient evidence was claimed; it returned uncertain. Observed. | Exact numerical agreement plus successful command are the likely completion affordance. Inferred. | Prior structural observations plus independent recomputation and comparison. Observed. |
| First unsafe assumption | None established; the run is incomplete, not unsafe. | Task category words were treated as adequate authority for a whole-line parser. Observed. | None in the preserved route; one run is insufficient to prove general safety. |

### Predeclared interpretation of new rows

For each new log sample, first classify: (1) whether the first model turn
obtained representation evidence, (2) whether any method-bearing command cites
only earlier observations or explicit task facts, (3) whether a command uses an
unknown representation fact discovered inside that same command, (4) whether
the stated method and executed command agree, and (5) whether the final verdict
follows independent execution evidence. A provider-invalid row remains invalid
measurement rather than a model-quality row.

## Ranked hypotheses

1. **Observation-order / same-command discovery and execution** — high. Sample 2 authored a parser before raw lines were returned; sample 3 observed raw lines first and used a direct structural parser.
2. **Completion affordance from a successful combined command** — high. Sample 2's command emitted a perfect comparison, then the final record described the method more strongly than the command warranted.
3. **Verifier charter lacks an explicit before-method dependency** — medium. It requires raw inspection but does not make it a prerequisite to parser design; the full Solver charter did express that ordering.
4. **Round-budget pressure** — medium. The configured maximum is three inspection rounds. Sample 1 used auto-read plus listing before any raw-line read or recomputation. The retained intermediate model text is missing, so it is unknown whether it believed a further execution request was still available.
5. **Method-to-command coherence** — high contributor. Sample 2's final description and command diverged. The present method-validity record is retrospective and content-blind.

## Controlled next experiment

Evaluator-only observation-order ablation. Keep model, effort, frozen workspace, Architect configuration, evaluator, tools and scoring unchanged. Change only the interaction schedule: turn one accepts read-only observation requests only; turn two may execute verification; turn three synthesizes. The evaluator instruction must remain generic and cannot name task-specific fields, syntax, or commands.

Pass: 3/3 correct and structurally grounded log methods. If 2/3, exactly one unchanged replication is permitted. If 0/3 or 1/3, stop and return to the next-ranked causal hypothesis. The image row remains separately invalid if provider output is ambiguous.
