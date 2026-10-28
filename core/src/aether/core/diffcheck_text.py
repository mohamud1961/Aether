"""What the differential check says: the author's briefs and the notes the solver sees (see diffcheck)."""

ISOLATED_BRIEF = """Someone else is working on the task below in another container; you will never see their work and \
they will not see yours. This container is a copy of the task's environment as it was before they started. Your job: \
write an executable check that compares a candidate solution's actual behaviour against the best source of truth \
this task makes available.

1. List each behaviour the task requires, quoting the task.
2. Identify the sources of truth available from the task and the files it supplies: an original implementation or \
program to stay equivalent to, a supplied evaluator or data, a documented format or interface, or a definition in \
the task you can compute directly. Prefer executing supplied originals over re-implementing them.
3. Build a reference for the required behaviour from those sources.
4. Choose inputs that discriminate: typical cases, boundaries, unusual combinations, and inputs beyond the examples \
the task gives.
   Where the task leaves a convention open (a tensor or matrix layout, an ordering, a number or text format, a \
rounding, an argument convention), do not pick one: accept every reading the task's wording allows, and flag a \
behaviour only if it is wrong under all of them.
5. Write {dir}/check.py: `python3 {dir}/check.py --candidate PATH` runs the candidate at PATH (a copy of the file \
the task asks for, possibly at a different path) and the reference on the same inputs, through the interface the \
task specifies, prints each disagreement as input / expected / actual, and exits 1 on any disagreement, 2 if the \
check itself could not run, 0 if none. Under {check_s} seconds.
6. Write the absolute path of the file the task asks for (the candidate to check) as the only line of \
{dir}/target.
7. Validate: write {dir}/good_candidate.<ext> that follows the task (check exits 0) and \
{dir}/broken_candidate.<ext>, a plausible but wrong variant (check exits 1). The harness re-runs both and uses \
your check only if they behave so.

Rules: keep everything you make under {dir}; do not create the task's deliverable at its real path. Call finish when \
the check is validated. There is no network.

The task:
{task}"""

FOUND_ISOLATED = """[independent check: {target} disagrees]
A check written by a separate run of the same model, from the task text alone, in a copy of the container taken \
before you started (it never saw your work or reasoning; it can be wrong), ran your file and reported:
{output}
Its source is at {copy} (it may rely on files that exist only in its own container)."""
AGREES_ISOLATED = "[independent check: {target} now agrees with it]"
FINISH_HOLD = "\nYour finish has not taken effect. If the check is wrong, say why and finish again; a second finish takes effect."


AUTHOR_BRIEF = """The author and solver currently share an unrestricted container. The author may see or change the \
candidate, and a prompt cannot enforce separation. Do not describe a result as independent. Separating one supplied \
good/broken pair demonstrates only discrimination of those two samples, not correctness of the check's oracle. Your \
task, if an isolated runtime explicitly enables it, is to write an executable check from task-supplied sources.

1. List each behaviour the task requires, quoting the task.
2. Identify the sources of truth available from the task and the files it supplies: an original implementation or \
program to stay equivalent to, a supplied evaluator or data, a documented format or interface, or a definition in \
the task you can compute directly. Prefer executing supplied originals over re-implementing them.
3. Build a reference for the required behaviour from those sources.
4. Choose inputs that discriminate: typical cases, boundaries, unusual combinations, and inputs beyond the examples \
the task gives.
   Where the task leaves a convention open (a tensor or matrix layout, an ordering, a number or text format, a \
rounding, an argument convention), do not pick one: accept every reading the task's wording allows, and flag a \
behaviour only if it is wrong under all of them.
5. Write {dir}/check.py: `python3 {dir}/check.py --candidate PATH` runs the candidate at PATH and the reference on \
the same inputs, through the interface the task specifies, prints each disagreement as input / expected / actual, \
and exits 1 on any disagreement, 2 if the check itself could not run, 0 if none. Under {check_s} seconds.
6. Write the absolute path of the file the task asks for (the candidate to check) as the only line of \
{dir}/target.
7. Validate: write {dir}/good_candidate.<ext> that follows the task (check exits 0) and \
{dir}/broken_candidate.<ext>, a plausible but wrong variant (check exits 1). The harness re-runs both and uses \
your check only if they behave so.

Rules: create, change or delete nothing outside {dir}. This is not enforced by the current shared environment. \
Do not report isolation or oracle correctness based only on the sample pair.

The task:
{task}"""

FOUND = """[candidate check result, provenance unverified: {target} disagrees]
The candidate check reported this difference (the check may be wrong):
{output}
This check separated one supplied good/broken pair; that does not establish oracle correctness. Re-run it: \
python3 {check} --candidate {target}"""
AGREES = "[candidate check result, provenance unverified: {target} agrees with the check; this does not establish task correctness (python3 {check} --candidate {target})]"
INCONCLUSIVE = "[candidate check inconclusive, provenance unverified: {target}: {reason}]"
