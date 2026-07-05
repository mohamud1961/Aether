# Architect-Only Eval Report

Scope: old ContractArchitect vs Runtime Workbench Architect on official task prompts/workspace maps.
Official test/grader excerpts are saved as review context only; they are not sent to the architect model.

| task | old score | overall | solver | verifier | config | key missing |
|---|---:|---:|---:|---:|---:|---|
| filter-js-from-html | 0/8 | 9.67/10 | 9/10 | 10/10 | 10/10 | manual_query_memory_ritual_present |
| sparql-university | 0/8 | 9.67/10 | 9/10 | 10/10 | 10/10 | solver_prompt_mentions_validate |
| openssl-selfsigned-cert | 0/8 | 10.0/10 | 10/10 | 10/10 | 10/10 | none |
| video-processing | 0/8 | 8.67/10 | 6/10 | 10/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_submit |
| install-windows-3.11 | 0/8 | 9.67/10 | 9/10 | 10/10 | 10/10 | solver_prompt_mentions_do_not_submit |
| fix-git | 0/8 | 9.67/10 | 9/10 | 10/10 | 10/10 | manual_query_memory_ritual_present |
| gpt2-codegolf | 0/8 | 9.0/10 | 7/10 | 10/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_do_not_submit, manual_query_memory_ritual_present |
| extract-moves-from-video | 0/8 | 8.67/10 | 6/10 | 10/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit |
| git-multibranch | 0/8 | 9.33/10 | 8/10 | 10/10 | 10/10 | solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit |
| configure-git-webserver | 0/8 | 9.33/10 | 8/10 | 10/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_do_not_submit |
| qemu-alpine-ssh | 0/8 | 8.67/10 | 7/10 | 9/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit, verifier_prompt_too_short_for_elite_contract |
| financial-document-processor | 0/8 | 9.0/10 | 9/10 | 9/10 | 9/10 | parseable HarnessConfigIR, parseable HarnessConfigIR, parseable HarnessConfigIR |
| vulnerable-secret | 0/8 | 9.67/10 | 9/10 | 10/10 | 10/10 | manual_query_memory_ritual_present |
| query-optimize | 0/8 | 9.0/10 | 7/10 | 10/10 | 10/10 | solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit |
| hf-model-inference | 0/8 | 9.33/10 | 8/10 | 10/10 | 10/10 | solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit |

## Notes

### filter-js-from-html

- Old missing: parseable TaskContract
- Overall: 9.67/10
- Solver prompt: 9/10 missing=manual_query_memory_ritual_present
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 493
- Verifier prompt words: 351
- Solver role: verification-first workspace investigator and deliverable assembler for an initially unspecified /app task
- Verifier role: adversarial evidence-bound completion gate for a workspace with no visible task specification
- Workflow: Inspect the provided envmap, workspace root /app, and any task-bearing files or instructions that become visible; treat the empty tree as evidence, not as a cue to invent work. / If a real task spec is discovered, extract exact deliverables, target paths, acceptance criteria, and runtime assumptions before editing anything. / If no spec exists, stop planning implementation and prepare a blocked-by-missing-spec result with no writes. / When a concrete deliverable exists, read the minimal necessary files first, then edit only the target artifacts and keep changes tightly scoped. / Use run_command only when a deliverable or validator truly needs execution; prefer the actual interpreter or tool present, and if Python is needed use python3 when python is absent. / After each write, validate the changed artifact with the lightest meaningful check, then inspect diffs for unintended changes. / If automatic memory surfaces a prior read, check, write, or command, reuse that evidence, narrow the next action, or justify a repeat only if state changed.
- Self-verification: Confirm whether a real specification exists in the current context before any implementation claims. / Check that every written file maps to an explicit discovered requirement and an intended path. / Verify the artifact with an executable or structural check that is relevant to the actual deliverable, not merely a syntax or existence check unless the deliverable is purely structural. / Confirm the workspace diff contains only intended changes and no placeholder or speculative files. / If blocked, verify that no files were modified and the report states the missing-spec condition precisely.
- Evidence requirements: Inspection evidence of the workspace and the presence or absence of a concrete task specification. / If a deliverable exists, path-specific artifact evidence plus a meaningful validation result. / If blocked, explicit evidence that no actionable spec exists and that no files were written. / Every claim must be anchored to a concrete path, diff, observation, or check result.
- False-positive risks: Interpreting an empty prompt as permission to invent scope. / Creating placeholder artifacts to look productive. / Using file existence or syntax checks as proof of an unspecified semantic task. / Claiming completion without path-specific evidence. / Assuming the initial empty tree proves no task exists without adequate inspection.
- Minimum completion evidence: Either a discovered deliverable path with a written artifact and successful validation, or inspection evidence showing no specification exists plus confirmation that no files were modified. / A bounded conclusion that distinguishes discovered-task completion from blocked-by-missing-spec. / No unresolved mismatch between reported deliverable and observed workspace state.

### sparql-university

- Old missing: parseable TaskContract
- Overall: 9.67/10
- Solver prompt: 9/10 missing=solver_prompt_mentions_validate
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 461
- Verifier prompt words: 303
- Solver role: Evidence-first workspace inspector and no-op executor for an underspecified task.
- Verifier role: Adversarial verifier for an empty-task/no-op run.
- Workflow: Inspect /app and any instruction-bearing files with read_file or run_command to confirm whether any concrete task artifact exists; do not assume hidden content. / If a concrete deliverable exists, extract its exact path, acceptance conditions, and required output before editing; if none exists, classify the run as under-specified and do not fabricate work. / Make no filesystem changes unless a specific task artifact is discovered; prefer a verified no-op over placeholder scaffolding or guessed content. / If memory or prior evidence indicates a repeated empty inspection, reuse that evidence and narrow the next check to hidden files or stop; do not re-read unchanged paths without justification. / Before submit, verify that the workspace remains unchanged, no stray processes were launched, and the final statement is tied directly to observed evidence.
- Self-verification: Run one authoritative workspace inspection and, only if needed, a hidden-file sweep to establish the actual state of /app. / Confirm that no files were written, modified, or left behind as placeholder artifacts. / Confirm that no background process was launched for the task. / Confirm that the final conclusion explicitly states whether a concrete task was found or whether the run was under-specified. / If any artifact or instruction is discovered, re-evaluate from the new evidence before submitting; do not submit on assumptions.
- Evidence requirements: A fresh inspection of the workspace root or /app showing the actual task state. / An explicit statement that no actionable task was found if the workspace remains empty/underspecified. / Confirmation that no files were created, modified, or left as placeholder artifacts. / No unresolved processes or other side effects from the inspection workflow.
- False-positive risks: Mistaking an empty visible tree for proof without actually inspecting the filesystem. / Submitting a generic completion note with no path-level evidence. / Creating a placeholder file that makes the run look productive but adds no real deliverable. / Assuming hidden instructions exist and fabricating a solution around them. / Using unsupported checks or external assumptions as if they were authoritative proof.
- Minimum completion evidence: One authoritative workspace inspection result. / A clean no-write/no-modification confirmation. / A final no-op conclusion tied to the inspection evidence.

### openssl-selfsigned-cert

- Old missing: parseable TaskContract
- Overall: 10.0/10
- Solver prompt: 10/10 missing=none
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 656
- Verifier prompt words: 394
- Solver role: Discovery-first workspace solver for an underspecified, possibly empty repository.
- Verifier role: Adversarial evidence-bound verifier for a discovery-first workspace task.
- Workflow: Begin with a workspace inventory from /app, including hidden entries, metadata, and any files that could encode a task such as README, instructions, tests, manifests, lockfiles, or dotfiles. Because the visible file tree is empty, treat the visible listing as incomplete and use run_command for directory enumeration if the filesystem read tools cannot show hidden entries. / Read only the smallest set of files needed to identify the real objective, required outputs, constraints, and acceptance criteria. Prefer task-bearing files over broad browsing, and if automatic memory reports that a read already happened, reuse that evidence rather than re-reading unless the file is expected to have changed or a narrower read will reveal different information. / If a concrete task emerges, translate it into exact deliverables, file paths, and protected areas before editing. Write down what must exist, what must change, and what must remain untouched so that validation is against the discovered contract rather than a guessed one. / Implement the minimum change set. Keep patches focused, avoid placeholder scaffolding, and preserve unrelated files. If the task is service-based or executable, launch or probe a process only after confirming from the workspace that such a process is actually part of the task. / Validate with the most direct supported evidence available: file existence or content assertions for static outputs, run_command for executable behavior, and inspect_checks or run_check when harness-owned checks exist. If a language runtime is needed, use the exact interpreter or CLI that the environment probe or command discovery actually shows; if python is absent but python3 is present, use python3 in both guidance and checks. / If no actionable task material exists after broad inspection, do not fabricate a solution or placeholder deliverable. Instead produce a blocked state that explicitly states what was inspected, what was absent, and why no safe artifact can be inferred.
- Self-verification: Confirm that every claimed deliverable path exists and was reread after the final write. / Confirm that every check you cite directly exercised the changed artifact, not an unrelated file or a generic environment probe. / Confirm that no step depends on hidden grader logic, unseen fixtures, or network access that the environment does not permit. / If automatic memory surfaced a prior read, check, or write, make sure any repeat was justified by a changed file, a narrower target, or a genuinely new expected signal. / Before submit, ensure the result is either a verified artifact set or a grounded blocked report, never a mix of speculation and partial evidence.
- Evidence requirements: A workspace inventory or equivalent evidence showing what was inspected, including hidden files if the tree was empty. / A grounded statement of the actual task or a grounded blocked finding. / Any claimed deliverable path with proof of creation, modification, and readback. / Any direct check result for executable or semantic claims, or a clearly stated local-verification limit if no safe check exists.
- False-positive risks: Mistaking an empty visible file list for complete absence of task material. / Treating source-text similarity or file presence as success when semantics matter. / Using unverified writes or unstated paths as evidence. / Assuming hidden grader expectations or external network access.
- Minimum completion evidence: Workspace inspection evidence and either task identification or a blocked rationale. / At least one verified artifact path if anything was changed. / At least one direct check for any executable or semantic claim, or an explicit local-verification limit if no safe check exists.

### video-processing

- Old missing: parseable TaskContract
- Overall: 8.67/10
- Solver prompt: 6/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_submit, solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 406
- Verifier prompt words: 371
- Solver role: workspace inspector and no-op completion guard
- Verifier role: adversarial workspace auditor for an underspecified task
- Workflow: Inspect the provided environment facts first: the empty task prompt, the visible tree under `/app`, and any environment-probe results. / If a concrete deliverable target appears in workspace files or memory, switch to building only that target; otherwise do not create placeholder files or scaffolding. / Use the smallest possible reads to confirm state; if automatic memory shows a repeated read/check/write collision, reuse the prior evidence, narrow the scope, justify the repeat, or change strategy instead of rerunning the same empty inspection. / Before submission, verify that no unauthorized writes, launches, or service probes occurred and that there are no pending harness checks that still need attention. / If later evidence reveals a real deliverable, define the exact path and validation plan before writing anything, and only then proceed.
- Self-verification: Confirm the visible workspace still has no task-specific files or directories beyond what was originally observed. / Confirm no files were written and no processes or services were started. / Confirm the completion note explicitly states that the prompt exposed no concrete deliverable. / If any check or write was performed, tie it to a concrete path and evidence result; otherwise do not claim behavioral validation.
- Evidence requirements: Workspace inspection evidence showing the visible tree state under `/app`. / An explicit no-deliverable determination unless a real target is later discovered. / No-write/no-launch evidence, or exact path-specific justification for any written artifact. / If a concrete target emerges, artifact path plus validation evidence for that target.
- False-positive risks: Assuming the empty prompt means the job is done without inspecting the workspace. / Writing placeholder files or notes and mistaking them for legitimate deliverables. / Treating unsupported smoke tests as authoritative completion evidence. / Missing a later-discovered instruction file because repeated inspection was not narrowed or justified.
- Minimum completion evidence: A confirmed survey of the visible workspace state. / A clear statement that no concrete deliverable is specified in the visible prompt/workspace. / Evidence that no unauthorized writes, launches, or service probes occurred. / No pending checks or unresolved findings remain before submit.

### install-windows-3.11

- Old missing: parseable TaskContract
- Overall: 9.67/10
- Solver prompt: 9/10 missing=solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 519
- Verifier prompt words: 433
- Solver role: Workspace-integrity and environment-probe solver for an under-specified, fileless task.
- Verifier role: Adversarial verifier for an under-specified workspace-integrity task.
- Workflow: Start by inspecting the task context, especially envmap.environment_probe and the visible file tree, to determine whether any explicit deliverable exists; because the probe is empty here, use run_command only as needed to establish basic runtime facts such as shell availability, current directory, and whether python or python3 is present. / Treat the visible workspace as the whole truth set unless later inspection reveals hidden instructions or files; with no visible files and no stated deliverable, do not invent an output artifact, do not install dependencies, and do not write anything by default. / If hidden instructions or additional artifacts appear, read only the minimum relevant paths, infer exact deliverable paths before editing, and keep the change set as small as possible. / When executable validation is needed, prefer direct semantic checks over source-text checks; if python is absent but python3 is available, use python3 for any script-based validation or helper logic. / Before submitting, confirm that no unintended writes occurred, inspect diffs or artifact history for accidental edits, and ensure the final state matches either a clean no-op or a completed explicit deliverable with evidence.
- Self-verification: Confirm the runtime probe captured usable command/interpreter availability and the workspace state before any write. / Confirm no new files or directories were created unless an explicit deliverable required them. / If you inspect the same empty workspace twice, justify the repeat only if the state changed; otherwise reuse the prior evidence and narrow the action. / If any build or test step was needed, rerun the smallest executable check that proves the intended behavior and compare its result to the expected state. / Ensure the final submission reflects either under-specified no-op with evidence or a completed deliverable; do not claim success from empty-tree inspection alone.
- Evidence requirements: Environment probe or shell probe evidence for available runtime/tooling. / Workspace inspection evidence showing the visible tree and whether any files were present. / No-write evidence via diff/history or equivalent, unless a real deliverable was intentionally created. / If a deliverable later appears, artifact-level validation evidence for that deliverable.
- False-positive risks: Claiming success from an empty directory listing alone. / Creating an unnecessary artifact that makes the workspace non-empty. / Assuming python is present without probing and then validating the wrong interpreter path. / Treating source-text or syntax checks as sufficient for semantic work. / Masking lack of progress by repeating the same inspection after memory already captured it.
- Minimum completion evidence: A successful runtime probe. / A workspace state snapshot. / A clean diff/history or equivalent proof that no unintended writes occurred, or explicit artifact validation if a real deliverable was present.

### fix-git

- Old missing: parseable TaskContract
- Overall: 9.67/10
- Solver prompt: 9/10 missing=manual_query_memory_ritual_present
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 529
- Verifier prompt words: 411
- Solver role: Verification-first scope triage solver for an underspecified empty workspace.
- Verifier role: Adversarial verifier for an undefined-scope, empty-workspace task.
- Workflow: Inspect the task prompt and the live environment facts first; treat the blank prompt, empty envprobe, and zero-file tree as the primary evidence boundary, not as a puzzle to fill in. / Look for any explicit deliverable only if it is actually present in inspected evidence; if the tree remains empty, do not invent files, tests, services, or target paths. / If a concrete artifact later appears in additional context, implement the smallest correct change at the exact discovered path, then validate that artifact with the most direct available check. / When automatic memory or history indicates a repeated read, check, or write, use the prior evidence instead of repeating the same action; narrow to the delta, justify the repeat, or switch strategy. / Before finalizing, confirm that the workspace state matches the claim, that no speculative edit was made, and that any completion language is limited to what was actually observed.
- Self-verification: Confirm the prompt is empty and no concrete deliverable path is specified anywhere in the inspected evidence. / Confirm the visible workspace is empty and that no file write was performed unless a real artifact became justified by inspection. / If any artifact was created, inspect its exact contents and rationale; if none was needed, ensure the final response explicitly states the task is underspecified or no-op. / Use harness checks only when they can validate a real artifact or workspace state; do not invent a nonexistent check or treat source-text-only evidence as semantic proof for a behavioral task. / Do not assume Python, Python3, or any other runtime from silence; only rely on probed availability if execution becomes necessary.
- Evidence requirements: A grounded statement that the task prompt is empty and no concrete deliverable is specified. / A grounded statement that the visible workspace is empty and no target files are present. / No speculative writes, placeholder artifacts, or invented validation claims. / If any repeat inspection occurs, evidence that prior memory/history was used to avoid redundant work. / A final response that clearly distinguishes observed facts from any inference.
- False-positive risks: Claiming completion for a task that was never specified. / Creating placeholder files and mistaking them for deliverables. / Assuming hidden tests, hidden files, or hidden services exist and drive the solution. / Using an empty envprobe to infer runtime availability. / Treating a no-op as success without explicitly grounding it in the inspected emptiness.
- Minimum completion evidence: Inspection-backed confirmation that the prompt is blank and the file tree has no visible files or dirs. / Confirmation that no unsupported edits were made. / A final grounded no-op or blocked conclusion that matches the observed state.

### gpt2-codegolf

- Old missing: parseable TaskContract
- Overall: 9.0/10
- Solver prompt: 7/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_do_not_submit, manual_query_memory_ritual_present
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 438
- Verifier prompt words: 342
- Solver role: workspace intake auditor and evidence-first no-op executor
- Verifier role: adversarial auditor for empty-task and empty-workspace runs
- Workflow: Start from the provided task prompt and visible environment, not assumptions; if the prompt is empty and the tree is empty, treat that as the primary signal. / If any future files or instructions appear, inspect only the minimal authoritative sources needed to determine a concrete deliverable before writing anything. / Classify the situation as either a real deliverable to build or a no-op/blocker case; do not blend the two. / When automatic memory reports a prior read, write, or failed check on the same target, reuse that evidence instead of repeating the action unless the question has changed. / Only if a concrete deliverable exists, build it and then run the smallest validation that directly supports its behavior or content.
- Self-verification: Confirm the final response explicitly states the task is missing or non-actionable when that is the evidence. / Confirm no placeholder files, dummy artifacts, or speculative edits were created. / Confirm every claim about workspace contents is backed by inspection evidence. / Confirm no unavailable runtime, package, or service assumption was made. / Confirm you did not confuse an empty workspace with a completed implementation.
- Evidence requirements: The solver output must state that the task prompt is empty or non-actionable. / The solver output must reflect the empty visible workspace and no deliverable files. / The solver output must not claim success through hidden assumptions or placeholder artifacts. / If any file artifact is produced, its presence must be justified as part of a genuine deliverable, not a filler report.
- False-positive risks: A polished response that never acknowledges the empty prompt. / Creating a dummy file or note file to look productive. / Treating the absence of files as evidence of completion without stating the blocker. / Claiming hidden instructions or hidden tests without evidence. / Overvalidating with repeated reads of already empty paths.
- Minimum completion evidence: A final solver message explicitly naming the missing-specification condition. / Evidence that the workspace root was empty when checked. / Evidence of no file writes or only necessary writes tied to a real deliverable. / A clear statement that no further local validation is possible beyond workspace inspection because no concrete artifact exists.

### extract-moves-from-video

- Old missing: parseable TaskContract
- Overall: 8.67/10
- Solver prompt: 6/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit, manual_query_memory_ritual_present
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 419
- Verifier prompt words: 430
- Solver role: Verification-first no-op task solver and environment auditor
- Verifier role: Adversarial verifier for empty-specification and no-op completion states
- Workflow: Inspect the provided task prompt, envmap file tree, and envmap.environment_probe before taking any action. / If the tree remains empty and no deliverable is named, classify the run as a no-op or blocked-by-spec state rather than guessing a task. / If later context reveals a concrete artifact, narrow to the smallest relevant file or subtree and gather evidence before writing anything. / Prefer read-only inspection; use run_command only when a concrete validation target exists and runtime availability has been probed. / If you write anything, record why the path exists, what requirement it satisfies, and how it will be verified; otherwise leave the workspace unchanged.
- Self-verification: Confirm no invented file names, outputs, or requirements appear in your reasoning or final note. / Confirm any repeated inspection is justified by a changed state or a new evidence need, not by habit. / Confirm no writes were made unless a concrete deliverable existed and a verification path was available. / Confirm the final completion note explicitly distinguishes absence of specification from tool failure and does not claim unearned success.
- Evidence requirements: A run summary explicitly stating that the task prompt is empty and the visible /app tree contains no files or directories. / A no-op or blocked-by-spec conclusion that does not fabricate deliverables or hidden benchmarks. / If any file is changed, a path-specific justification and verification plan tied to a concrete requirement; otherwise an explicit statement that no writes occurred.
- False-positive risks: Treating the empty workspace as a completed implementation. / Inventing an artifact path or test fixture to make the task look concrete. / Using command success without a meaningful validation target as proof of completion. / Failing to mention the absence of a task specification and thereby implying a fabricated assignment. / Writing placeholder files to show activity when the correct outcome is to remain unchanged.
- Minimum completion evidence: Explicit confirmation that the task prompt is empty and the workspace is visibly empty. / An explicit statement that no deliverables were created because no concrete requirement exists. / Evidence that no unsupported writes were made, or a fully justified write tied to a real requirement if one later appears.

### git-multibranch

- Old missing: parseable TaskContract
- Overall: 9.33/10
- Solver prompt: 8/10 missing=solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 497
- Verifier prompt words: 370
- Solver role: Inspection-first no-op solver for an empty workspace
- Verifier role: Adversarial verifier for an empty-workspace no-op task
- Workflow: Begin by inspecting the visible workspace root and any environment probe information. Establish whether any task-specific files, instructions, fixtures, or pending checks exist before taking any action. / Because the current file tree is empty, treat the absence of inputs as the working hypothesis, not as proof. If you need to disambiguate hidden entries or dotfiles, use one bounded run_command listing of the workspace root; do not broaden into exploratory shell work. / If no task artifact or instruction is discovered, do not create placeholder files, do not scaffold a solution, and do not guess at hidden requirements. The correct action is to preserve the clean workspace and prepare a concise evidence-based no-op completion. / If a legitimate task artifact appears later, read the minimum necessary path once, record what changed, and keep the scope narrow to that path. Do not read the same empty state repeatedly unless the tree changed or a new path is now justified. / Use harness-owned checks only if they are present and relevant. Inspect the available checks first; run only those checks that the harness exposes, after inspection and before submit. Do not invent checks or treat ad hoc shell commands as authoritative validation.
- Self-verification: Confirm that no files were written, edited, or deleted. / Confirm that the visible workspace remains empty or otherwise unchanged from the initial inspection. / Confirm that no deliverable path exists and no pending harness check remains unaddressed. / Confirm that any summary you provide is grounded in an actual inspection result, not a generic refusal or an assumption about hidden requirements.
- Evidence requirements: Workspace inspection evidence for /app or the visible root state. / Explicit confirmation that no files were written, edited, or deleted. / Explicit statement that no task-specific deliverable or instruction was present. / Any harness check result, or an explicit note that no relevant check existed. / If run_command was used to disambiguate hidden entries, a minimal summary of that result.
- False-positive risks: Assuming an empty visible tree is automatically sufficient without inspection evidence. / Producing a placeholder artifact to mark completion. / Treating a generic refusal as a verified no-op. / Relying on syntax or source-text checks for a task whose success is behavioral workspace state. / Overlooking hidden pending checks or unverified changes.
- Minimum completion evidence: A concrete root-workspace inspection result. / A no-write/no-edit/no-delete confirmation. / A concise statement that no task-specific inputs or deliverables were found. / No unresolved harness check evidence.

### configure-git-webserver

- Old missing: parseable TaskContract
- Overall: 9.33/10
- Solver prompt: 8/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 397
- Verifier prompt words: 334
- Solver role: Workspace triage and underspecification-respecting solver
- Verifier role: Adversarial verifier for an empty-prompt, empty-workspace task
- Workflow: Start by inspecting the provided facts: empty task prompt, envmap environment probe, and the empty workspace tree at /app; treat the absence of visible files as a real observation, not an excuse to guess deliverables. / Use the minimum necessary probing to learn runtime availability only if it changes the plan; prefer run_command for shell and interpreter probing, and if python is absent but python3 exists, use python3 for any scripts or checks. / Search only for explicit task evidence or named artifacts. Do not recursively hunt for a phantom assignment, and do not create placeholder files unless a concrete spec is discovered. / If a concrete deliverable spec appears, implement only that spec, record the exact path(s) touched, and validate with the smallest safe local checks that actually exercise the artifact. / Before submitting, confirm that every claim is supported by evidence, that any repeated read/check/command/write was justified by new context, and that the result is either a validated artifact or a clean no-op conclusion.
- Self-verification: Confirm no hidden assumption about filenames, deliverables, or grader behavior was introduced. / Confirm any runtime probe results are sufficient to justify the chosen course of action. / Confirm no file was written unless a concrete spec required it. / Confirm any ad hoc scripted validation uses python3 if python is unavailable. / Confirm the final state can be explained entirely from observed evidence, not guesswork.
- Evidence requirements: Environment probe or equivalent runtime facts consulted before action. / Workspace inventory confirming that no visible task artifacts were present before any edits. / Explicit conclusion stating either that no concrete spec exists or that a concrete spec was discovered and satisfied. / If any artifact was created, the artifact path and a validation result that matches the discovered spec.
- False-positive risks: Writing a generic placeholder artifact and calling it completion. / Claiming success without first checking the provided environment facts and workspace state. / Using unsupported or invented smoke tests as proof. / Treating an empty workspace as proof that the task was solved rather than underspecified.
- Minimum completion evidence: Empty-workspace confirmation. / Environment-probe awareness or equivalent runtime fact used in decision making. / An explicit conclusion that no concrete spec exists, or a verified artifact if a spec was discovered. / No unvalidated file writes.

### qemu-alpine-ssh

- Old missing: parseable TaskContract
- Overall: 8.67/10
- Solver prompt: 7/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit
- Verifier prompt: 9/10 missing=verifier_prompt_too_short_for_elite_contract
- Config contract: 10/10 missing=none
- Solver prompt words: 340
- Verifier prompt words: 290
- Solver role: No-op workspace steward and verification-first triager.
- Verifier role: Adversarial verifier for a blank-prompt no-op task.
- Workflow: Treat the provided envmap as authoritative: /app is empty in the visible tree, so do not assume hidden deliverables or invent a target artifact. / Do not start by writing files or launching processes; first determine whether any later context actually introduces a concrete task artifact. If none exists, stop building and preserve the clean workspace. / If later context or a tool result reveals files, inspect only the explicit paths needed for the task, then make the minimum edit set required. / When automatic repeat interception indicates you are about to inspect the same empty tree or repeat a failed check, do not re-run it blindly; reuse the prior evidence, narrow the inspection, justify the repeat, or change strategy. / Never create placeholder code, docs, manifests, or scaffolding to fill an empty prompt.
- Self-verification: Confirm that the current prompt does not specify any deliverable path and that no files were created, edited, or deleted. / Check that the final response explains the no-op rationale instead of claiming an implementation or hidden artifact. / Before submit, ensure there were no unnecessary command, process, or write actions taken just to prove the workspace is empty.
- Evidence requirements: Explicit acknowledgement that the visible /app tree is empty and the task prompt contains no deliverable. / Evidence that no files were written, edited, or deleted. / A final response that states the result is a deliberate no-op rather than an implementation.
- False-positive risks: Treating an empty prompt as automatically solved without stating the no-op basis. / Creating placeholder files, docs, or scaffolding to simulate progress. / Assuming a hidden task or hidden grader requirement without evidence. / Using source-text or syntax checks as proof of completion for a task with no artifact to validate.
- Minimum completion evidence: A grounded no-op explanation tied to the blank prompt and empty /app tree. / No workspace mutations of any kind. / No claim that a deliverable was built or that hidden requirements were satisfied.

### financial-document-processor

- Old missing: parseable TaskContract
- Overall: 9.0/10
- Solver prompt: 9/10 missing=parseable HarnessConfigIR
- Verifier prompt: 9/10 missing=parseable HarnessConfigIR
- Config contract: 9/10 missing=parseable HarnessConfigIR
- Errors: old=[] workbench=["background job resp_0bc3bb525c270a89006a43e6bd525881968bb0af22eed85c91 incomplete with no usable text: IncompleteDetails(reason='max_output_tokens')"]

### vulnerable-secret

- Old missing: parseable TaskContract
- Overall: 9.67/10
- Solver prompt: 9/10 missing=manual_query_memory_ritual_present
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 523
- Verifier prompt words: 404
- Solver role: verification-first discovery-and-implementation solver for an underspecified empty-workspace task
- Verifier role: adversarial verifier for an underspecified empty-workspace task
- Workflow: Start with the smallest safe discovery pass using run_command to inspect /app and any obvious task manifests, because the visible tree is empty and environment_probe is blank; do not assume python, shells, or modules beyond what you actively probe. / Read only the minimum files needed to identify the real objective, deliverables, protected paths, and any validation expectations; if a file or path was already inspected and automatic memory surfaces that fact, avoid rereading unless the target state could have changed. / If a concrete deliverable appears, map it to exact output files before writing anything, then edit only those files and keep diffs minimal and intentional. / Use supported local validation after each meaningful change; prefer harness-visible checks when available, otherwise use run_command for narrowly targeted syntax, content, or behavior checks that directly exercise the artifact. / If no actionable task is discoverable after a bounded, evidence-driven inspection, stop building, do not create speculative files, and prepare a no-op submission that clearly states the absence of a concrete task. / When the automatic memory system reports a repeat collision, narrow the inspection to the changed scope, reuse the prior evidence, or justify the repeat with a concrete state-change reason rather than re-running the same broad read/check.
- Self-verification: Confirm every claimed deliverable exists at the claimed path and matches the discovered instruction set. / Inspect the diff and ensure there are no incidental edits, placeholder files, or touched protected paths. / If code, scripts, or config were changed, run the narrowest relevant local check that can actually fail on the changed artifact. / If the task remains undefined, verify that the workspace is still clean and that no write occurred. / Before submit, make sure each validation result corresponds to a real artifact and not just to reasoning about source text.
- Evidence requirements: A workspace discovery trail that shows the solver inspected for instructions or manifests. / If anything was created, the claimed output path and the content/state evidence for that artifact. / A validation result or a clean-no-op diff showing there were no unintended writes. / Any repeat reads or checks must be justified by changed state or narrowed scope.
- False-positive risks: An empty workspace being mistaken for a completed task. / A no-op claim made without first inspecting the workspace. / Source-text compliance being mistaken for actual artifact success. / Speculative or placeholder files being treated as deliverables. / Repeated checks on the same unchanged path being mistaken for validation.
- Minimum completion evidence: At least one inspection result showing the workspace or task manifests were examined. / Either an implemented artifact with validation evidence or a clean no-op conclusion with no writes. / No unexpected changes outside the claimed scope.

### query-optimize

- Old missing: parseable TaskContract
- Overall: 9.0/10
- Solver prompt: 7/10 missing=solver_prompt_too_short_for_elite_contract, solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 446
- Verifier prompt words: 329
- Solver role: Evidence-first workspace triage solver for empty or underspecified tasks.
- Verifier role: Adversarial auditor for empty-task submissions; verify that the solver either correctly no-ops or clearly reports why no concrete deliverable can be produced.
- Workflow: Inspect the live task context and visible workspace state first; treat the session as degenerate if the prompt remains empty and the tree has no files or directories. / If any concrete artifact appears, read only the minimum relevant paths and identify the exact deliverable; otherwise do not invent one. / Do not assume Python, Python3, packages, or services exist when env probe data is absent; only probe execution if a real artifact or runtime question emerges. / When automatic memory flags a repeated read, check, or write against the same empty state, reuse the prior evidence, narrow the scope, or change strategy instead of rerunning it. / Use harness-owned checks only when they can prove something about a real artifact; do not certify an empty workspace with syntax-only checks. / If the workspace stays empty after minimal inspection, prepare a concise no-op or clarification outcome instead of creating placeholder files or fake validation.
- Self-verification: Confirm the prompt is still empty or underspecified and no concrete deliverable path exists in visible context. / Confirm no files were written, overwritten, deleted, or created as placeholders. / If any command or check was run, confirm it targeted a real artifact or concrete inspection need. / Confirm the final response states the evidence and does not claim fabricated outputs or hidden validations. / If a repeat inspection occurred, confirm it was justified by changed evidence rather than habit.
- Evidence requirements: A concise evidence-backed statement that the task prompt is empty or underspecified. / A concrete report of the visible workspace state showing no files or directories. / A no-change proof such as absence of writes or a clean diff/history. / A final no-op or clarification conclusion that does not invent outputs.
- False-positive risks: Assuming the absence of visible files automatically means the task is solved without stating evidence. / Writing placeholder artifacts to manufacture progress. / Claiming verification without any actual inspection evidence. / Inferring hidden runtime capabilities from an empty environment probe. / Treating a generic summary as proof of completion.
- Minimum completion evidence: Empty-task or underspecified-task acknowledgement. / Visible empty-workspace acknowledgement. / No writes or workspace changes recorded. / A deliberate no-op or clarification decision grounded in the evidence.

### hf-model-inference

- Old missing: parseable TaskContract
- Overall: 9.33/10
- Solver prompt: 8/10 missing=solver_prompt_mentions_validate, solver_prompt_mentions_do_not_submit
- Verifier prompt: 10/10 missing=none
- Config contract: 10/10 missing=none
- Solver prompt words: 948
- Verifier prompt words: 520
- Solver role: You are a verification-first workspace investigator and implementer operating in /app. The prompt and visible tree are empty, so your first job is to discover the actual assignment from workspace artifacts and environment probes before changing anything. Treat any discovered README, TASK, INSTRUCTIONS, spec, manifest, or generated file as the authoritative contract if it clearly describes the work. Optimize for minimal, explainable edits and evidence-backed completion; do not invent requirements, do not guess hidden grader behavior, and do not declare success from a blank tree or from source-text inspection alone.
- Verifier role: You are an adversarial, evidence-bound verifier for a discovery-first workspace task with an empty prompt and an empty visible tree. Accept completion only when the solver has shown where the real assignment came from, what changed, and what local evidence supports correctness; reject optimistic narratives that are not tied to paths, diffs, or checks.
- Workflow: Survey the workspace root and any immediately discoverable instruction-bearing files or directories first, then expand only as needed; if no authoritative task source is visible, use lightweight discovery to locate hidden instructions or tests before editing. / Read the smallest set of files needed to identify the assignment, dependencies, expected artifacts, and any validation hooks; prefer artifacts that look like task specs, manifests, fixtures, or existing solution scaffolds over speculative source files. / If environment_probe is empty and you need an interpreter or CLI, probe availability only when it changes the validation plan; do not assume python, python3, or any package is present without checking. / Once the task is identified, plan the exact deliverables and edit only the files necessary to satisfy the discovered contract; keep a tight mental map of paths, inputs, outputs, and any protected or generated files. / Before writing, check for prior reads, prior diffs, or repeated evidence signals; if the same path or check has already been inspected and nothing changed, reuse the prior result instead of rereading or rerunning it, unless you can justify that the file changed or the earlier evidence is insufficient. / Implement the smallest coherent change set that fulfills the task; if code or config is required, keep it aligned with existing conventions and avoid incidental refactors. / After editing, perform validation that matches the task type: run available project checks, inspect artifacts, compare diffs, verify file presence/size/content, and if executable behavior matters, run the relevant local command or fixture-based check. / If a validation step fails, classify the failure precisely, inspect only the affected paths or logs, and repair the root cause rather than broadening the change set blindly. / If the workspace contains no visible clues and discovery remains inconclusive, continue searching for authoritative instruction sources or tests before making speculative edits; do not fabricate deliverables. / Prepare to submit only after you can tie each required deliverable to evidence from the task source and to a successful or safely bounded local verification result.
- Self-verification: Re-read every file you changed and confirm the final contents match the discovered requirement, with no accidental truncation, placeholder text, or syntax damage. / Inspect the diff for scope control: no unintended files changed, no protected paths touched, and no unrelated formatting churn unless it is required for the task. / If the task involves executable behavior, run the narrowest meaningful local check available and verify that the observed output or exit status matches the intended behavior; do not substitute syntax-only checks for semantic behavior. / Use file_exists, file_size, and content assertions only for deliverables that are genuinely file-based; if behavior is semantic or runtime-dependent, verify the behavior directly with the best safe local mechanism available. / Confirm that any repeated evidence came from a changed file or a narrower scope; if not, do not repeat the action again without a reason. / Before finalizing, ensure you can point to the authoritative instruction source, the modified artifact paths, and the concrete verification evidence for each required outcome.
- Evidence requirements: A discovered authoritative task source or a clearly bounded explanation of why none could be found after reasonable workspace discovery. / A minimal, path-specific diff showing the implemented changes under /app. / At least one task-appropriate local validation artifact or a justified limitation explaining why no safe local check can fully prove the remaining property. / A final state that is consistent with the discovered requirements and does not touch unrelated files.
- False-positive risks: Treating an empty tree or empty prompt as completion. / Confusing inspection of files with implementation of the assignment. / Using syntax or existence checks as proof for semantic behavior. / Leaving placeholder content, TODOs, or partial configs that look complete at a glance. / Making changes without tying them to a requirement source or without showing validation evidence.
- Minimum completion evidence: An authoritative instruction-bearing source or equivalent discovery evidence. / The final edited artifact paths with a compact change summary. / A passing local check, file assertion, or a specific bounded limitation explaining why the local check cannot prove the remaining property.
