# What actually goes wrong on our three failing dev tasks (offline trace study, 15 October 2026)

Asked for by the principal ("i need to understand what our main failure causes are and where and why"; "authority
check go"). Offline, no model calls, VM deallocated. Sources: N2 traces (Aether + GPT-6-Luna, 30 rows, rendered in
`core_judge_inputs.py`), grader assertions from the N2 trial directories, per-task pass counts from N1/N2/L2 results.

## Where

On the TB 2.1 development board, five tasks pass in nearly every run (net-fit, graph-query-catalog,
feal-differential, repair-history, dual-language-build). Three tasks hold nearly every failure, and every failure is a voluntary
finish with wrong work (no crash, no timeout): **binary-extract ≈ 0/19, construct-assembly ≈ 1/14, seq-assembly ≈ 3/16.**

## Why (from the traces)

| Task | What the agent did | Grader | Kind |
|---|---|---|---|
| binary-extract (6/6 N2 runs) | Read the binary-extract headers, saw `DYN (Position-Independent Executable)`, entry 0x1060, and **deliberately rebased every address to 0x400000** so the keys match the task's *format* example `{"4194304": ...}`. Its own check asserts the example key exists. The example's value at 0x400000 is not this file's binary-extract magic, so the example comes from a different binary. | 0.00% of expected values found | **Example over input:** a format example taken as content, against the file's own headers |
| seq-assembly | Installed primer3, **ran `oligotm` with the task's flags**, reported pair gaps ≤ 0.4–1.7 °C. | Pair gap 5.002 °C (66.8 vs 71.8); one run: BsaI site missing from a primer | **Definition:** "the part of the primer that anneals" measured on a different region than the grader's (likely the grader counts tail bases that also match the template; not confirmed, VM off) |
| construct-assembly | Mixed: antigen inferred wrongly (HRAS instead of FLAG, the target is never found in other runs); PDB sequences trimmed to fit the 3,000-nt limit; molecule binder chosen as MGMT. Two runs **name the open doubt in their final message** ("antibody target remains unverified", "not fully confirmed") and finish anyway. | Start must be FLAG; order flag–donor–dhfr–acceptor–snap | **Domain inference** + **constraint conflict resolved by editing**, + **finishing with a stated doubt** |

## What this means for the proposed authority check

My earlier framing ("the agent substituted its own version of what the task named") was partly wrong:
- seq-assembly: the agent **did** use the named tool; an "run the named authority" check changes nothing.
- binary-extract: a check "reproduce the task's example" would **reinforce** the error. The authority is the input
  file; the example is format. A generic check "are my keys in the input's own address space / consistent with the
  input's own metadata" would catch it, but the agent already read that metadata and overrode it.
- construct-assembly: an exact-match check against the named sources (PDB FASTA) catches the trimmed-sequence run only.

**Expected yield of an authority check on these failures: low** (binary-extract uncertain, construct-assembly 1 run, seq-assembly none).
Not built. Recorded as a failed hypothesis before spending anything.

## The causes, as types (generic, not task rules)

1. **Example over input:** a format/illustrative example in the task outranks the actual input the agent has.
2. **Measurement definition:** a stated quantity measured on a region/definition the grader does not use.
3. **Domain inference:** a fact the task leaves to the agent (which construct-assembly an antibody binds) inferred wrongly.
4. **Conflict resolved silently:** two constraints cannot both hold (exact sequence vs length); the agent edits one.
5. **Finishing with a stated doubt:** the agent's own summary names an unverified point and it finishes.

Types 4 and 5 are visible in the agent's own words; 1 is visible in its own code comment ("rebased to the
conventional 0x400000"); 2 and 3 are not visible without the grader's convention or the domain fact.
