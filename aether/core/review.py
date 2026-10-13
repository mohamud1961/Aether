"""Independent finish review by the reviewer, over task-visible state only.

When the solver calls ``finish``, the reviewer is shown the task, the solver's latest
actions with their real outputs, and a fresh snapshot of the workspace taken by
the harness. It is never shown the solver's own summary or claims (in the
offline bench, the claim-free review caught 15/18 wrong finishes vs 10/18 with
claims). The question set is the earlier claim ledger's failure-mode question (the variant with the
measured solve lift) plus one completeness question per task criterion.

A review failure is never silent: it is returned as status "error" with the
reason, recorded in the trace and the run record, and the finish proceeds. An
answer outside its question's choices, or a confidence outside [0, 1], makes the
whole response an error; a criterion left unanswered is reported as unconfirmed.
A "pass" means no failure mode crossed the hold threshold; ``unmet`` lists what the
reviewer could not confirm, so pass with unmet is not "verified".
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import shlex
from typing import Any, Callable, Mapping, Sequence

from .questionnaire import (QUESTIONNAIRE_SCHEMA, BAD_MODES, FAILURE_DETAILS, FAILURE_MODES,
                            FAILURE_QUESTION_ID, failure_question, _wire_question, compact, split_criteria)
from .env import CONTROL_DIR, Environment, run

REVIEW_MODEL = "reviewer"
MAX_REQUEST_BYTES = 15_000
MAX_TASK_CHARS = 3_000
HOLD_CONFIDENCE = 0.8
COMPLETENESS_CHOICES = ("direct_and_current", "indirect", "self_written_check_only", "none", "contradicted")
COMPLETENESS_DETAILS = {
    "direct_and_current": "The evidence directly shows the requirement holds in the current state.",
    "indirect": "The evidence only bears on the requirement indirectly.",
    "self_written_check_only": "Only a check the solver wrote itself supports it; nothing independent does.",
    "none": "No evidence bears on the requirement.",
    "contradicted": "The evidence shows the requirement does not hold.",
}
# Every criterion the reviewer cannot see holding directly is reported, not only the contradicted ones
# (C2b row 1: a never-run interpreter was judged "indirect" on every criterion, so the solver was told
# "done with unverified parts" with nothing listed).
UNCONFIRMED = {"contradicted": "the evidence shows it does not hold", "none": "no evidence",
               "self_written_check_only": "only your own check supports it",
               "indirect": "evidence only indirect", "unanswered": "the reviewer gave no answer"}
Transport = Callable[[dict[str, Any]], Mapping[str, Any]]
# The verifier reads program output from the sandbox itself, not only what the solver last looked at
# (C2 row 1: the solver saw garbled stdout four times; the reviewer saw none of it).
MALFUNCTION_QUESTION_ID = "malfunction"
MALFUNCTION_CHOICES = ("none_seen", "garbled_or_binary_output", "errors_or_crashes", "wrong_or_suspicious_values",
                       "unknown")
MALFUNCTION_DETAILS = {
    "none_seen": "No output in the evidence suggests anything is malfunctioning.",
    "garbled_or_binary_output": "Output contains garbled characters or binary bytes where readable text is expected.",
    "errors_or_crashes": "Output shows error messages, failed operations, crashes or aborted runs.",
    "wrong_or_suspicious_values": "Output shows values that look wrong or implausible.",
    "unknown": "The evidence is insufficient to tell.",
}
MALFUNCTION_RELATION = ("Does any program output in the evidence (including the terminal log tails, where "
                        "non-printing bytes are shown as ^@ or M- sequences) show signs that something is "
                        "malfunctioning?")
LOG_TAIL_BYTES = 1_500


@dataclass
class Verdict:
    status: str  # "pass" | "hold" | "error"
    mode: str = ""
    confidence: float = 0.0
    unmet: list[str] = field(default_factory=list)
    reason: str = ""
    request_bytes: int = 0
    answers: dict[str, Any] = field(default_factory=dict)
    malfunction: str = ""
    malfunction_confidence: float = 0.0

    def malfunction_line(self) -> str:
        if self.malfunction in ("", "none_seen", "unknown"):
            return ""
        return (f"It also sees signs of malfunction in program output: {MALFUNCTION_DETAILS[self.malfunction]} "
                f"(confidence {self.malfunction_confidence:.2f}). Look at the full output (the terminal logs "
                "hold all of it) and explain or fix it.")

    def feedback(self) -> str:
        lines = [
            "[independent review] A separate reviewer examined the current workspace and your recent "
            "command outputs (it did not see your summary).",
            f"Its judgement: {FAILURE_DETAILS.get(self.mode, self.mode)} (confidence {self.confidence:.2f}).",
        ]
        if self.unmet:
            lines.append("Requirements it could not confirm from the evidence:")
            lines += [f"- {u}" for u in self.unmet[:6]]
        if self.malfunction_line():
            lines.append(self.malfunction_line())
        lines.append("Check these against the real state. Fix what is missing, or, if you are certain the task "
                     "is complete, demonstrate it with a command whose output shows it and call finish again.")
        return "\n".join(lines)


async def output_tails(env: Environment, control_dir: str = CONTROL_DIR) -> str:
    """Tail of every terminal log and of the newest REPL cell output, non-printing bytes made visible."""
    q = shlex.quote
    cmd = (f"for f in {q(control_dir)}/term/*/out.log $(ls -t {q(control_dir)}/repl/out/*.log 2>/dev/null | head -1); "
           f"do [ -f \"$f\" ] || continue; echo \"$ tail $f\"; tail -c {LOG_TAIL_BYTES} \"$f\" | cat -v; echo; done")
    res = await run(env, cmd, timeout_s=30)
    return res.stdout[:8000]


async def snapshot(env: Environment, workdir: str, written: Sequence[str]) -> str:
    """Read-only workspace facts gathered by the harness, not by the solver."""
    q = shlex.quote
    files = " ".join(q(p) for p in list(written)[-8:])
    cmd = (f"cd {q(workdir)} 2>/dev/null; echo \"$ pwd: $(pwd)\"; echo '$ ls -la'; ls -la 2>&1 | head -40; "
           "if git rev-parse --git-dir >/dev/null 2>&1; then echo '$ git status --short'; "
           "git status --short 2>&1 | head -30; echo '$ git log --oneline -3'; git log --oneline -3 2>&1; fi")
    if files:
        cmd += f"; for f in {files}; do echo \"$ head $f\"; ls -la \"$f\" 2>&1; head -c 600 \"$f\" 2>&1; echo; done"
    res = await run(env, cmd, timeout_s=30)
    return (res.stdout + ("\n" + res.stderr if res.stderr else ""))[:6000]


def build_request(task: str, actions: Sequence[str], state: str, *, criteria_mode: str = "complete_v1",
                  budget: int = MAX_REQUEST_BYTES, outputs: str = "") -> tuple[dict[str, Any], list[dict[str, str]]]:
    criteria = split_criteria(task, mode=criteria_mode)
    for n_actions, limit, n_criteria, state_chars in ((8, 900, 12, 5000), (6, 600, 12, 3500), (5, 400, 8, 2500),
                                                       (4, 300, 6, 1800), (3, 200, 4, 1200), (2, 150, 3, 800)):
        views = {f"a{i + 1}": compact(a, limit) for i, a in enumerate(actions[-n_actions:])}
        views["state"] = compact(state, state_chars)
        if outputs:
            views["output_logs"] = compact(outputs, state_chars)
        refs = list(views)
        crit = criteria[:n_criteria]
        texts = {c["criterion_id"]: c["text"] for c in crit}
        questions = {FAILURE_QUESTION_ID: _wire_question(failure_question(refs), texts),
                     MALFUNCTION_QUESTION_ID: _wire_question({
                         "relation": MALFUNCTION_RELATION, "choices": list(MALFUNCTION_CHOICES),
                         "choice_details": MALFUNCTION_DETAILS, "evidence_refs": refs}, texts)}
        for c in crit:
            questions[f"completeness:{c['criterion_id']}"] = _wire_question({
                "relation": f"Classify whether the evidence directly and currently establishes requirement "
                            f"{c['criterion_id']}.",
                "choices": list(COMPLETENESS_CHOICES), "choice_details": COMPLETENESS_DETAILS,
                "criterion_id": c["criterion_id"], "evidence_refs": refs}, texts)
        request = {"model": REVIEW_MODEL, "state": {
            "schema": QUESTIONNAIRE_SCHEMA, "raw_task": task[:MAX_TASK_CHARS], "criteria": crit,
            "claim_card": None, "visible_evidence": views}, "questions": questions}
        if _bytes(request) <= budget:
            return request, crit
    raise ValueError(f"review request cannot fit {budget} bytes")


def _bytes(request: Mapping[str, Any]) -> int:
    return len(json.dumps(request, allow_nan=False, separators=(",", ":")).encode())


def _choices(qid: str) -> Sequence[str] | None:
    if qid == FAILURE_QUESTION_ID:
        return FAILURE_MODES
    if qid == MALFUNCTION_QUESTION_ID:
        return MALFUNCTION_CHOICES
    if qid.startswith("completeness:"):
        return COMPLETENESS_CHOICES
    return None


def answers_of(response: Any) -> dict[str, dict[str, Any]]:
    """The validated answers. Raises ValueError on anything malformed (review() turns that into status error)."""
    if not isinstance(response, Mapping):
        raise ValueError("the reviewer response is not an object")
    result = response.get("result")
    answers = result.get("answers") if isinstance(result, Mapping) else response.get("answers")
    if not isinstance(answers, Mapping):
        raise ValueError("the reviewer response has no answers")
    out = {}
    for qid, raw in answers.items():
        qid = str(qid)
        allowed = _choices(qid)
        if allowed is None:
            continue  # a question we did not ask
        if not isinstance(raw, Mapping) or raw.get("choice") not in allowed:
            raise ValueError(f"answer to {qid} is not one of its choices: {str(raw)[:120]}")
        confidence = raw.get("confidence")
        if (isinstance(confidence, bool) or not isinstance(confidence, (int, float))
                or not 0.0 <= float(confidence) <= 1.0):
            raise ValueError(f"answer to {qid} has confidence {confidence!r}, not a number in [0, 1]")
        out[qid] = {"choice": raw["choice"], "confidence": float(confidence)}
    if FAILURE_QUESTION_ID not in out:
        raise ValueError("the reviewer did not answer the failure-mode question")
    return out


def judge(answers: Mapping[str, Mapping[str, Any]], criteria: Sequence[Mapping[str, str]],
          request_bytes: int) -> Verdict:
    mode = answers[FAILURE_QUESTION_ID]
    texts = {c["criterion_id"]: c["text"] for c in criteria}
    unmet = []
    for cid in texts:
        choice = answers.get(f"completeness:{cid}", {}).get("choice", "unanswered")
        if choice in UNCONFIRMED:
            unmet.append(f"{cid} ({UNCONFIRMED[choice]}): {compact(texts[cid], 240)}")
    broken = answers.get(MALFUNCTION_QUESTION_ID, {})
    malfunction, m_conf = str(broken.get("choice") or ""), float(broken.get("confidence") or 0.0)
    # Only the failure-mode reading holds a finish. A malfunction finding informs (progress and final reviews)
    # but does not hold: the log tails include errors the solver already fixed, and in D1 it held two correct
    # finishes (feal-differential: AssertionErrors from early exploratory cells) and no wrong one.
    hold = mode["choice"] in BAD_MODES and mode["confidence"] >= HOLD_CONFIDENCE
    return Verdict("hold" if hold else "pass", mode["choice"], mode["confidence"], unmet,
                   request_bytes=request_bytes, answers=dict(answers), malfunction=malfunction,
                   malfunction_confidence=m_conf)


async def review(transport: Transport, env: Environment, *, task: str, workdir: str,
                 actions: Sequence[str], written: Sequence[str], call, control_dir: str = CONTROL_DIR) -> Verdict:
    """``call`` runs the blocking transport off the event loop (asyncio.to_thread in production)."""
    try:
        state = await snapshot(env, workdir, written)
        outputs = await output_tails(env, control_dir)
        request, criteria = build_request(task, actions, state, outputs=outputs)
        response = await call(transport, request)
        return judge(answers_of(response), criteria, _bytes(request))
    except Exception as exc:  # surfaced, never silent: see module docstring
        return Verdict("error", reason=f"{type(exc).__name__}: {str(exc)[:300]}")
