# Independent review of the Step 0 report

Status: **exploratory counts require qualification; no paid accuracy gate is
established**. This is a code-contract review and metadata-only inventory; it
does not re-open any task trace or inspect any sensitive-named JSON file.

## Observed detector failures

The local qa/step0_contract_reproduction.py imports the delivered detector
source and exercises it with synthetic inputs. It reproduces these failures:

1. “Python is installed” is classified as a missing-command belief, and a
   successful Python command is reported as contradicting that belief.
2. Python and Python 3 are collapsed to one name. A successful Python 3
   command is not by itself evidence that the Python command exists.
3. Any memory reading is treated as contradicting a statement of insufficient
   memory, even though the required amount is unknown.
4. A still-running command with no exit receipt can be marked as a passing
   check and its mentioned filename as checked.
5. A Python command that performs ordinary task work can match the
   “environment probe” pattern. A matched step is not an avoidable step.

These controls demonstrate possible false positives, not their prevalence in
the 500-run corpus. Together with Claude's independently found S2 false hit,
they mean the counts cannot establish how many failures are convertible or
that decisive errors leave no mechanical trace. The reported median of three
probe-matched steps is not a measured three-step saving.

The inventory script also falls back to reward-like fields in summary JSONs if
a trial reward is unavailable. The permitted outcome labels are reward.txt and
the reward field of result.json; how many reported rows used the fallback has
not been reconciled. The independent dc1 reward recount on the allowed labels
still matches N 4/11, S 4/11 and X 3/11; it does not validate blind secondary
labels, missing rows or all-in cost.

## Data handling

The inventory source recursively attempts to open every JSON under its data
root and reads every discovered trace. A filename-only walk found five JSON
filenames containing a sensitive term and 146 trace paths in task families
previously excluded by our conservative visibility filter. Those 146 are not
all credential tasks. No file content was opened in this review, and the
presence of credential values or their transfer to a model provider is
unknown. A sensitive-looking filename is not proof the file contains a key.
The data copy is hard-linked to the original archive; it is not an independent
backup. Do not alter those files or inspect their contents.

## Decision

Continue the user-requested Core state implementation and offline controls.
The preregistered three-task accuracy prerequisite has not been demonstrated;
do not treat it as either a proven negative mechanism or authority to run the
accuracy board. The median estimated model charge is not an all-in upper bound
for provider failures, infrastructure, parallel calls or the £5 envelope.
Select future targets with reliable task-facing evidence and correct-work
controls before spending. No new model, network or VM work was used in this
review.

Sources: research/core_mission_20261028/step0/STEP0.md, its CLAUDE_REVIEW.md
and scripts/inventory.py, env_beliefs.py and signatures.py in the Claude
mission worktree, and the metadata-only reproduction above.
