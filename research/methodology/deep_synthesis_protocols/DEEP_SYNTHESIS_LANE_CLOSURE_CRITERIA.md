# Deep Synthesis Lane Closure Criteria

Use this file when deciding whether a lane is wave-sufficient.

The core rule is simple:

- a strong-looking file is not enough
- a long file is not enough
- a lane is only wave-sufficient when the required depth artifacts for that lane exist for the active domain and the main analyst has actually synthesized them

## 1. Shared rule for all lanes

A lane may count as wave-sufficient only if all of the following are true:

- the lane answered the active wave question rather than drifting into generic summary
- the lane cites concrete repo-local evidence
- direct observation is separated from inference
- `coverage_not_yet_used` is explicit
- the lane does not silently overclaim beyond what it actually read
- the lane’s main analyst, not a support artifact, wrote the final synthesis
- the principal can assign a saturation status to the promoted families:
  - `exploratory`
  - `emerging`
  - `decision_ready`

## 2. Trajectory and Failure Lane

Minimum requirements for wave-sufficient status:

- per-run analysis for the promoted run slice
- cross-run or shared-task comparison for the active domain
- pass/fail divergence analysis where the active domain shows meaningful spread
- failure-point comparison where a failure story is promoted
- explicit linkage to visible source or architecture where available
- explicit `behavioral reconstruction` caveats where source is not available
- at least one saved support artifact when the wave depends on large-run inventory or matrix work
- at least one trajectory-to-source case study for each major source-backed family promoted in the wave

## 3. Codebase and Source-Reconstruction Lane

Minimum requirements for wave-sufficient status:

- subsystem mapping for each promoted major source family in the wave
- architecture notes for control doctrine, state/context, verification, recovery, and environment policy where relevant to the domain
- explicit separation between first-class systems and secondary or archive-only captures
- explicit handling of `src_cod_*` pressure without silently turning archive hints into source-backed fact
- at least one saved support artifact when the wave depends on large repo triage or file discovery
- dedicated source-system dossier coverage for every first-class system materially promoted in the wave

## 4. Literature and Formal Lane

Minimum requirements for wave-sufficient status:

- active-domain formal routing into:
  - anchor dossier
  - theme dossier
  - inventory-only
- explicit note of unread, weakly extracted, or low-quality papers that limit confidence
- formal claims tied to the active domain rather than loose literature summary
- formal contradictions or tensions preserved when sources disagree
- at least one anchor or theme dossier cited when the formal lane materially affects promoted claims

## 5. Informal, Issues, and Postmortems Lane

Minimum requirements for wave-sufficient status:

- active-domain cluster routing across informal, issues, and postmortems
- contradiction-pressure clusters identified explicitly
- separation between operator philosophy, issue evidence, and direct failure reports
- explicit caveats for low-credibility or weakly captured sources
- at least one informal cluster dossier cited when the lane materially pressures promoted claims

## 6. Eval and Benchmark Lane

Minimum requirements for wave-sufficient status:

- explicit routing of benchmark, verifier, judge, grader, replay, and local-eval surfaces that materially affect the wave
- separation between benchmark-name familiarity and actual evaluator understanding
- explicit note of unread or weakly captured eval families
- at least one eval or benchmark dossier cited when the lane materially affects promoted claims

## 7. What does not close a lane

These do not count as lane closure on their own:

- a long first-pass output
- repeated mentions of the same mechanism family
- a support artifact without main-agent synthesis
- a sampled paper or issue slice treated as broad coverage
- a source hint being treated as source-backed implementation
- “the wave feels strong”

## 8. Principal decision rule

If a lane misses these requirements, the principal must do one of:

- open a governed same-wave follow-up
- carry the missing work forward explicitly into a later vertical wave
- mark the wave incomplete for acceptance purposes
