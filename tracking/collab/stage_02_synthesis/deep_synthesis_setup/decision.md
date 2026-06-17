# Deep Synthesis Setup Decision

Status: updated; execution surface now aligned to the compressed 14-wave model

Opened: 2026-04-02

Updated: 2026-04-07

Artifact

- `deep_synthesis_setup`

Current judgment

- The Deep Synthesis setup surface now assumes:
  - `4` main agents for serious mechanism and failure waves
  - optional `eval/benchmark` fifth lane
  - bounded support sub-agents as standard lane infrastructure
  - Gemini and Claude at gates, not as default parallel main lanes

Completed state reflected by setup

- `mechanism_map` Wave 01 complete as legacy anchor
- `mechanism_map` Wave 02 accepted with carry-forward warnings

Next move

- refresh the operator packet/prompt surface against this setup
- then open `mechanism_map` Wave 03 `verification_completion_and_recovery`
