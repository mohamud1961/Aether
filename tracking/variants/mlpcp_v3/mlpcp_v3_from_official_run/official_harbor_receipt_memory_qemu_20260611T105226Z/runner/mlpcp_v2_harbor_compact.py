from __future__ import annotations

from typing import Any


def clip_text(value: object, limit: int = 700) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: limit // 2] + "\n...[truncated]...\n" + text[-limit // 2 :]


def compact_execute_result_for_cockpit(result: dict[str, Any]) -> dict[str, Any]:
    compact_actions = []

    for item in result.get("action_results") or []:
        res = item.get("result") or {}
        compact_res: dict[str, Any] = {}

        if isinstance(res, dict):
            for key in ("exit_code", "passed", "path", "safe_summary"):
                if key in res:
                    compact_res[key] = res[key]
            if "stdout_excerpt" in res:
                compact_res["stdout_excerpt"] = clip_text(res.get("stdout_excerpt"), 900)
            if "stderr_excerpt" in res:
                compact_res["stderr_excerpt"] = clip_text(res.get("stderr_excerpt"), 900)
            if "content" in res:
                compact_res["content_excerpt"] = clip_text(res.get("content"), 900)
            if "matches" in res:
                compact_res["matches"] = list(res.get("matches") or [])[:40]
        else:
            compact_res["value"] = clip_text(res, 500)

        receipt_ref = item.get("receipt_ref") or {}
        compact_actions.append({
            "action_id": item.get("action_id"),
            "action_type": item.get("action_type"),
            "status": item.get("status"),
            "summary": clip_text(item.get("summary"), 300),
            "failure_class": item.get("failure_class"),
            "error": clip_text(item.get("error"), 500) if item.get("error") else None,
            "receipt_ref": {
                "ref_id": receipt_ref.get("ref_id") if isinstance(receipt_ref, dict) else None,
                "summary": clip_text(receipt_ref.get("summary"), 200) if isinstance(receipt_ref, dict) else None,
            },
            "result": compact_res,
        })

    finalization = result.get("finalization") or {}
    compact_finalization = None
    if isinstance(finalization, dict):
        compact_finalization = {
            "allowed": finalization.get("allowed"),
            "failure_class": finalization.get("failure_class"),
            "summary": clip_text(finalization.get("summary"), 300),
            "unresolved_obligations": [
                {
                    "check_id": x.get("check_id"),
                    "requirement_id": x.get("requirement_id"),
                    "failure_class": x.get("failure_class"),
                    "summary": clip_text(x.get("summary"), 220),
                }
                for x in (finalization.get("unresolved_obligations") or [])[:5]
                if isinstance(x, dict)
            ],
        }

    return {
        "request_id": result.get("request_id"),
        "status": result.get("status"),
        "stopped_at_action_id": result.get("stopped_at_action_id"),
        "action_results": compact_actions[:10],
        "finalization": compact_finalization,
    }
