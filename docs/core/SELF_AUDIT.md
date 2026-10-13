# Full engineering self-audit — 13 October 2026

Scope: engineering-only steps 1–6 of the approved Core plan. The principal explicitly excluded new GLM
runs and required no subagents/browser. GPT-6-Astra performed this review personally; this is not a fresh
second-agent review. Confidence comes from adversarial real effects, failed-before controls, an
installed wheel and independent deterministic artifact grading, not implementation self-report.
Entry checkpoint: 32432e560. Final executable source: d0192a38bf3fd5c3ed86083f26d2eb532958b6af.

## Accepted findings and closure

| ID | Reproduced or inspected defect | Repair and acceptance | Disposition |
|---|---|---|---|
| A1 | Failure after real REPL startup or a failed closer bypassed other cleanup | Whole setup/loop has one finally boundary; independent owned closers; original error and cleanup errors retained; end trace after cleanup. Real REPL failure and independent-closer controls failed before | Repaired; lifecycle tests |
| A2 | File transfer could exceed run deadline; clone host calls had separate long bounds | DeadlineEnvironment applies the same remaining work budget to exec/upload/download; clone host operations use it; cleanup has its own bounded reserve. Blocked-transfer control failed before | Repaired; lifecycle and Linux deadline/cancel tests |
| A3 | Missing usage became zero; unanswered requested criterion could leave a clean review | Per-field null accounting through Harbor, all roles/attempts; exclusive call namespace; all requested criteria required; failed/cancelled/open attempts retained | Repaired; truth, adapter, HTTP and native Harbor records |
| A4 | Early stream EOF accepted an executable partial call; stream closure omitted | Incomplete stream fails without dispatch; partial content/call/identity retained; close attempted on success/error/cancel. Early-EOF control failed before; real AsyncOpenAI HTTP path exercised | Repaired; lifecycle and HTTP tests |
| A5 | Whitespace paths changed; blank lines treated as binary; long-line tail inaccessible | Exact paths; valid text detection; bounded UTF-8 pages with byte offset and continuation | Repaired; real-file controls failed before; file and Linux tests |
| A6 | Cut upload damaged existing bytes; permission failures could be hidden | Stage bytes beside target, preserve permissions before atomic commit, follow file symlinks; failed transfers preserve old bytes/mode | Repaired; interrupted real-upload control failed before |
| A7 | Configured mirror paths/indirect shell edits not faithfully read back; mutable aliases changed originals | Publish/read back configured mirrors every turn; trace accepted edit text; deep independent original snapshots; stable read_history pages even if HISTORY file save fails | Repaired; planted observations and shell-variable edit controls |
| A8 | Cleanup/cancellation/transport failure could leak clones or orphan processes | Bound host operations, retain cleanup failure, clean named resources; central owned-root process-tree stop; zombie-aware liveness; restart without replaying raw keys | Repaired; real Docker creation-then-failure, clone cancellation, REPL background child and terminal Linux controls |
| A9 | Direct Docker tests did not exercise actual Harbor adapter | Real Harbor 0.20 Trial/environment/class + installed wheel + real SDK + localhost scripted endpoint + independent native shell grader; correct artifact and deliberately wrong artifact | Repaired; final native good/bad gate passed |
| A10 | Standalone package lacked current whole-tree installed validation and source custody | Self-contained src layout and lock; no research imports; bytewise wheel/source proof; full outside-repo suite; syntax/name lint and format | Repaired; final installed/Linux gates passed |
| A11 | Restarted terminal truncated the old log behind a previously returned handle | Generation-specific log roots, same logical terminal name; old path still returns old bytes. Real control failed before | Repaired; terminal tests |
| A12 | Confident reviewer “complete” set verified=true for an actually wrong file | verified remains null; reviewer_reports_complete records opinion separately; correctness belongs to independent grader. Wrong-artifact control failed before | Repaired; real-file loop test |
| A13 | Our A6 atomic-write repair moved the payload inside a directory and claimed success | Reject directory/symlink-to-directory; commit pathname with Linux mv -T (local non-Linux development uses os.replace), including a directory appearing during transfer. Before-control failed; 28 focused checks passed | Repaired; file controls and final Linux gate |
| A14 | A11 generation suffix collided with a valid independent terminal name | Separate generation with a dot, which the terminal-name alphabet excludes. Restart main while main-1 holds real shell state; the before-control loses state/log, the repair preserves both | Repaired; final terminal controls passed; final frozen Linux gate passed |
| A15 | Launch reply loss or initialization failure left a real shell outside cleanup ownership; restart dropped ownership before successful stop | Register launch root before dispatch, known PID before init, explicit ready state; resolve lost reply from the owned PID file; unresolved cleanup is an error; retain owner until stop succeeds. Both real-launch controls failed before, closed processes after | Repaired; final terminal controls passed; final frozen Linux gate passed |

A13 and A14 were introduced regressions caught during this self-audit. It is retained in the evidence and
lesson rather than hidden by the original broad pass. Every semantic repair has a realistic failure
control; no check was weakened to manufacture a pass. Root compatibility fixtures were corrected to
answer all requested criteria, preserving the stronger runtime contract.

## Faithfulness and design challenge

We opened implementations behind success signals. Files/shell/PTY/REPL/images and Docker resources are
real. Scripted providers are explicitly fixtures, never represented as GLM or real the reviewer responses.
Successful loop finish is submission, not correctness: the native wrong-artifact row must receive
reward zero. Missing usage stays null. Exact request reconstruction means decoded client JSON plus
actual received HTTP JSON, not arbitrary network-byte equivalence or a provider billing attestation.

Original review R1 (cancelled attempt disappears), R2 (partial response loss), and R3 (the reviewer finish veto)
are closed by truth/HTTP/loop controls. The former bridge reply timeout is not retroactively called a
receipt. User takeover superseded monitor ownership; no replacement Claude task or message was sent.

The smallest sufficient ownership structure remains: one loop for ordering/lifecycle, one provider
for transport, one call log for attempts, one environment boundary for deadlines/I/O/owned cleanup,
one context owner for immutable history versus editable view, and one Harbor adapter. Background work
uses named terminals; no second job-state service. Read batches have a single explicit opt-in and
write fences. More layers, retry services, universal world state or a skills framework would add
unearned complexity in this one-shot envelope. Formatting and stable interfaces help maintenance;
LOC and test totals are not a quality score.

## Consciously limited or rejected expansions

- **Universal crash resume:** outside the approved one-shot/clean-abort envelope. Attempt journals retain
  unfinished calls honestly; they do not guarantee coordinator resurrection or physical exactly-once effects.
- **Default concurrency/context/cap policy changes:** remain unselected. Deterministic tests establish
  mechanics; only a model comparison can establish useful decisions, no-harm or score/cost gains.
- **Cache optimization inferred from characters:** rejected as unsupported. Character prefixes are not
  token-cache eligibility. Recorded old telemetry and approximate replay cannot attribute a cache defect.
- **Every synthesis failure becomes a new mechanism:** rejected. Historical taxonomy is exploratory;
  it supplies diagnostic ideas, not current incidence or implementation authority.
- **Clone as full-world snapshot:** not claimed. Docker commit excludes bind mounts, process/network state;
  checks are fallible advisory observations of the declared filesystem copy. Isolation/mount limitations
  are explicit; no shallow name/timestamp fingerprint is presented as cryptographic integrity.
- **Always-hold on uncertain review:** rejected because it invents authority and can obstruct correct work.
  Malformed review is an explicit error; valid opinion is still fallible and cannot certify completion.
- **Live the reviewer/GLM qualification:** excluded by this engineering-only execution. Loopback HTTP tests prove
  transport/accounting/error handling, not current route availability, billed cost or reviewer accuracy.

No unresolved material accepted finding remains in the reviewed code. The final exact wheel passed 141 Linux checks, zero skips, and native Harbor correct/wrong controls
reward 1/0 with no exception and zero live model calls. The final outside-repo portable gate passed
119 checks with 22 explicit platform skips. No finite test set proves the aspiration “code
never hinders the model,” or eliminates semantic model failures. See VALIDATION.md for exact evidence.
