"""Request and factual note format for opt-in checkpoint v2."""
from __future__ import annotations

import json
import math
import re
import time
from typing import Any, Mapping, Sequence

from ..challenger_claim_types import QUESTIONNAIRE_SCHEMA
from ..progress_checkpoints import MAX_REQUEST_BYTES
from .progress_question import split_criteria

PREFIX = "progress_checkpoint_v2:"
STAGES = ("not_started", "exploring_only", "partial_not_runnable", "runnable_with_failures", "mostly_working", "appears_complete")
E2E = ("yes", "no", "unclear")
TRACK = ("likely", "uncertain", "unlikely")
CRITERION = ("met_in_observed_state", "partially_met", "not_met", "cannot_tell")
STILL = ("none", "build_or_job_running", "service_running", "unclear")
BOOL = ("yes", "no")


def purpose_class(tool: str, command: str = "") -> str:
    text = f"{tool} {command}".lower()
    if re.search(r"\b(sleep|wait|poll|job_wait)\b", text):
        return "wait"
    if re.search(r"\b(install|pip |npm i|apt |cargo add|go get)\b", text):
        return "install"
    if re.search(r"\b(test|pytest|unittest|check|verify|lint)\b", text):
        return "test"
    if re.search(r"\b(build|compile|make|cargo build|npm run build)\b", text):
        return "build"
    if tool in {"write_file", "edit_file"} or re.search(r"(>|\btee\b|\bsed -i\b|\bmv\b|\bcp\b|\btouch\b)", command):
        return "edit"
    if re.search(r"\b(run|start|serve|launch|execute)\b", text):
        return "run"
    return "explore"


_ERROR_LINE = re.compile(
    r"(?:\w*error\w*|failed|failure|exception|traceback|not found|denied)", re.I,
)
_NEGATED_ERROR_LINE = re.compile(
    r"\b(?:no|zero|without|0)\s+(?:(?:errors?|failures?)\b|\w+\s+(?:errors?|failures?)\b)",
    re.I,
)


def _first_error(receipt: Any) -> str:
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    # Keep explicit error channels first, but include stdout because test runners
    # commonly report failures there while leaving stderr empty. A line must have
    # a positive failure marker; negated summaries such as "0 errors" are not
    # evidence of a failure even if they contain the word "error".
    channels = (payload.get("stderr"), payload.get("error"), receipt.summary, payload.get("stdout"))
    for text in channels:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if line and _ERROR_LINE.search(line) and not _NEGATED_ERROR_LINE.search(line):
                return line[:240]
    return ""


def compressed_history(receipts: Sequence[Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows, outputs, signatures = [], [], {}
    for receipt in receipts:
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        tool = str(receipt.kind)
        if tool not in {"read_file", "read_file_page", "list_files", "search_files", "write_file",
                        "edit_file", "run_command", "job_output", "job_wait", "job_stop"}:
            continue
        command = str(payload.get("command", ""))
        args = command or str(payload.get("path") or receipt.summary or "")
        args = " ".join(args.split())[:120]
        err = _first_error(receipt)
        out = str(payload.get("stdout") or "")
        stderr = str(payload.get("stderr") or "")
        output_bytes = int(payload.get("stdout_bytes_total", len(out.encode())) or 0) + int(payload.get("stderr_bytes_total", len(stderr.encode())) or 0)
        purpose = purpose_class(tool, command)
        rows.append({"step": int(receipt.step), "tool": tool, "args": args,
                     "exit_code": payload.get("exit_code"), "first_error": err,
                     "output_bytes": output_bytes, "purpose": purpose})
        if err:
            signatures[err] = signatures.get(err, 0) + 1
        # Preserve the five latest action observations, regardless of tool kind.
        observation = payload.get("stdout") or payload.get("content") or payload.get("result") or receipt.summary
        outputs.append({"step": int(receipt.step), "tool": tool, "args": args,
                        "exit_code": payload.get("exit_code"),
                        "observation": str(observation), "stdout": out, "stderr": stderr})
    repeated = [{"signature": sig, "count": n} for sig, n in signatures.items() if n >= 3]
    return rows, repeated, outputs


def _lean_env(envmap: Any) -> dict[str, Any]:
    if envmap is None:
        return {}
    source = dict(envmap) if isinstance(envmap, Mapping) else {
        key: getattr(envmap, key) for key in ("workspace_root", "cwd", "shell", "python", "node", "available_capabilities")
        if hasattr(envmap, key)
    }
    secret = re.compile(r"key|token|secret|password|credential|authorization", re.I)
    result: dict[str, Any] = {}
    for key, value in source.items():
        if secret.search(str(key)):
            continue
        val = value
        if isinstance(val, (str, int, float, bool)) or val is None:
            result[str(key)] = val
        elif isinstance(val, Mapping):
            result[str(key)] = {str(k): v for k, v in val.items() if not secret.search(str(k)) and isinstance(v, (str, int, float, bool, type(None)))}
    return result


def checkpoint_questions(criteria: Sequence[Mapping[str, str]], refs: list[str]) -> dict[str, Any]:
    qs = {
        PREFIX + "stage": {"relation": "Classify the current stage using the observed state and action history.", "choices": list(STAGES)},
        PREFIX + "end_to_end_run_exists": {"relation": "Classify whether a complete end-to-end run is shown in the observed state and history.", "choices": list(E2E)},
        PREFIX + "on_track_for_remaining_time": {"relation": "Estimate whether the work is on track for the remaining time.", "choices": list(TRACK)},
        PREFIX + "still_running_work": {"relation": "Classify work that is still running from the observed process and service state.", "choices": list(STILL)},
        PREFIX + "repeating_failure": {"relation": "Classify whether the same failure is repeated in the action history.", "choices": list(BOOL)},
    }
    for row in criteria:
        cid = str(row["criterion_id"])
        qs[PREFIX + "criterion_status:" + cid] = {"relation": f"Classify criterion {cid} from observed state and history.", "choices": list(CRITERION), "criterion_id": cid}
    for spec in qs.values():
        spec["evidence_refs"] = refs
    return qs


def build_request(*, task_text: str, snapshot: Mapping[str, Any], receipts: Sequence[Any], envmap: Any,
                  fraction: int, elapsed_sec: float, remaining_sec: float,
                  model: str = "", success_contract: Sequence[Mapping[str, str]] = ()) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    criteria = [{"criterion_id": f"C{i+1}", "text": str(row["text"])} for i, row in enumerate(split_criteria(task_text, fallback=False))]
    history, repeated, outputs = compressed_history(receipts)
    env = _lean_env(envmap)
    state = {"schema": QUESTIONNAIRE_SCHEMA, "raw_task": str(task_text), "criteria": criteria,
             "observed_state": dict(snapshot), "compressed_action_history": history,
             "repeated_error": repeated, "last_five_outputs": outputs[-5:],
             "env_map": env, "older_full_outputs": outputs[:-5],
             "claims_by_solver": [dict(row) for row in success_contract] if success_contract else []}
    refs = ["observed_state", "compressed_action_history", "last_five_outputs"]
    questions = checkpoint_questions(criteria, refs)
    for check in success_contract:
        kid = str(check["id"])
        questions[PREFIX + "contract_status:" + kid] = {
            "relation": f"Classify success check {kid} from observed state and history.",
            "choices": list(CRITERION), "contract_id": kid,
        }
    criterion_text = {str(c["criterion_id"]): str(c["text"]) for c in criteria}
    wire = {}
    for qid, spec in questions.items():
        choices = list(spec["choices"])
        details = {choice: choice for choice in choices}
        cid = str(spec.get("criterion_id", ""))
        kid = str(spec.get("contract_id", ""))
        if cid:
            details = {choice: f"{choice}: {criterion_text.get(cid, cid)}" for choice in choices}
        elif kid:
            contract_check = next(row for row in success_contract if str(row["id"]) == kid)
            details = {choice: f"{choice}: {contract_check['description']} — {contract_check['observable']}" for choice in choices}
        relation = str(spec["relation"])
        wire[qid] = {"type": "choice", "criteria": details,
                     "instructions": relation + "\nCited evidence refs: " + ", ".join(refs)}
    request = {"model": str(model), "state": state,
               "checkpoint": {"fraction_percent": int(fraction), "elapsed_sec": round(elapsed_sec, 3), "remaining_sec": round(remaining_sec, 3)},
               "questions": wire}
    trim = {"dropped": [], "request_bytes": 0}
    def size() -> int:
        return len(json.dumps(request, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    while size() > MAX_REQUEST_BYTES and state["older_full_outputs"]:
        state["older_full_outputs"].pop()
        trim["dropped"].append("older_full_outputs")
    if size() > MAX_REQUEST_BYTES and state["env_map"]:
        state["env_map"] = {}
        trim["dropped"].append("env_map")
    if size() > MAX_REQUEST_BYTES:
        for output in state["last_five_outputs"]:
            output["observation"] = output["observation"][:400]
            output["stdout"] = output["stdout"][:400]
            output["stderr"] = output["stderr"][:400]
        trim["dropped"].append("last_five_output_excerpts")
    if size() > MAX_REQUEST_BYTES:
        raise ValueError("checkpoint v2 request exceeds the 120 KB limit after bottom-up trimming")
    trim["request_bytes"] = size()
    return request, questions, trim


def factual_note(*, fraction: int, remaining_sec: float, delivery_fraction: int,
                 answers: Mapping[str, Mapping[str, Any]], criteria: Sequence[Mapping[str, str]],
                 success_contract: Sequence[Mapping[str, str]] = (),
                 observation_start_fraction: float | None = None,
                 observation_end_fraction: float | None = None) -> str:
    def get(key: str) -> str:
        return str(answers[PREFIX + key]["choice"])
    statuses = ", ".join(f"C{i+1} {get('criterion_status:C'+str(i+1))}" for i, _ in enumerate(criteria))
    contract_statuses = ", ".join(
        f"{row['id']} {answers[PREFIX + 'contract_status:' + str(row['id'])]['choice']}"
        for row in success_contract
    )
    if contract_statuses:
        statuses = "; ".join(part for part in (statuses, contract_statuses) if part)
    if observation_start_fraction is None or observation_end_fraction is None:
        header = f"Progress check (triggered at {fraction}% / {round(remaining_sec)} s left; delivered at {delivery_fraction}%)"
    else:
        start = max(0.0, float(observation_start_fraction)) * 100
        end = max(start, float(observation_end_fraction) * 100)
        header = (f"Progress check (triggered at {fraction}%; state observed during {start:.1f}%–{end:.1f}% "
                  f"of elapsed time; {round(remaining_sec)} s left at trigger; delivered at {delivery_fraction}%)")
    return (header + "\n"
            f"stage: {get('stage')}; end-to-end run: {get('end_to_end_run_exists')}; "
            f"still-running work: {get('still_running_work')}; criteria: {statuses or 'none'}; "
            f"repeating failure: {get('repeating_failure')}; on track: {get('on_track_for_remaining_time')}")


def parse_answers(answers: Any, questions: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    parsed = {}
    for qid, spec in questions.items():
        row = answers.get(qid) if isinstance(answers, Mapping) else None
        if not isinstance(row, Mapping) or row.get("choice") not in spec["choices"]:
            raise ValueError(f"missing or invalid typed answer for {qid}")
        confidence = row.get("confidence")
        probs = row.get("probabilities")
        if isinstance(probs, Mapping) and row["choice"] in probs:
            confidence = probs[row["choice"]]
        if isinstance(confidence, bool):
            raise ValueError(f"invalid confidence for {qid}")
        confidence = float(confidence)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError(f"invalid confidence for {qid}")
        parsed[qid] = {"choice": str(row["choice"]), "confidence": confidence}
    return parsed
