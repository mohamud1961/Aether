# Glossary

| Term | Meaning |
|---|---|
| Harness | Everything around the model that turns it into an agent: loop, tools, context, verification, traces |
| Generation | One complete harness design. Five generations are recorded in `research/generations/` |
| Solver | The agent that works on the task |
| Verifier | An independent reviewer that judges the task state with read-only tools, never the solver's account |
| Architect | (Gen 3) a model that designs the workbench for one task: tools, prompts and checks |
| Official grader | The external check that scores a finished run. Never part of the harness or the loop |
| Task | A prompt, a workspace, a hidden grader, a reference solution and known-bad states |
| Known-bad | A wrong end state that a grader must reject with a named reason |
| Careless agent | A scripted shortcut (do nothing, fake it, skip the check, wrong target, half done) that must fail |
| Trial | One attempt by one agent on one task; one row in the results |
| Invalid row | A trial in which no real model work happened (launch failure, provider error); counted apart from failures |
| Board | A fixed list of tasks run under matched conditions for comparison |
| Arm | One configuration under comparison on a board |
| Sentinel | A named task that must not regress when a change is promoted |
| Pre-registration | A prediction, falsifier and promotion bar sealed before any trial |
| Held-out evaluation | Tasks kept closed to development and agents, run once against a sealed prediction |
| Receipt | A claim, its evidence and the check that produced it |
| Catch rate / false-hold rate | Share of wrong finishes a verifier holds / share of correct finishes it holds |
| Cost per solved task | Tokens, model calls and wall time spent per task actually solved |
