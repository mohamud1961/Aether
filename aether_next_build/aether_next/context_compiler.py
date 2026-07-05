"""Context compiler: builds the per-step context packet for the solver.

Extracted from ledger.py to stay under the 500-LOC cap.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .memory_events import artifact_history, memory_events
from .runtime_ir import stable_json

if TYPE_CHECKING:
    from .ledger import ExecutionLedger, Receipt
    from .monitors import MonitorAlert
    from .runtime_ir import CompiledRuntime, ContextPolicy, ContextRecipe


_STANDARD_SECTION_KEYS = (
    "open_obligations",
    "obligation_status",
    "monitor_alerts",
    "live_processes",
    "recent_progress",
    "failure_clusters",
    "artifacts_present",
    "candidate_leaderboard",
    "installed_capabilities",
    "planned_checks",
    "command_results",
)

_SUPPORTED_EXACT_RECIPE_SELECTORS = frozenset({
    *_STANDARD_SECTION_KEYS,
    "pending_checks",
    "active_verifier_findings",
    "repeated_actions",
    "files_already_read",
    "latest_file_reads",
    "memory_loop_feedback",
    "automatic_memory_findings",
    "no_progress_controls",
    "action_constraints",
    "stuck",
    "artifact_history",
    "memory_events",
    "latest_failure",
    "failed_checks",
    "observations",
})

_RECENT_RECIPE_SELECTORS = frozenset({
    "recent_progress",
    "tool_results",
    "file_reads",
    "file_writes",
    "command_results",
    "check_results",
    "query_memory_results",
    "verifier_results",
    "artifact_history",
    "observations",
})

_TOOL_RESULT_KINDS = frozenset({
    "read_file",
    "write_file",
    "run_command",
    "bootstrap",
    "process_launch",
    "service_probe",
    "process_stop",
    "artifact_inspection",
    "inspect_checks",
    "query_memory",
    "automatic_memory",
    "query_artifact_history",
    "inspect_diff",
    "record_observation",
    "experiment",
})


class ContextCompiler:
    def compile(
        self,
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        alerts: list["MonitorAlert"],
    ) -> dict[str, Any]:
        policy = compiled.context_policy
        available = self._available_sections(compiled, ledger, alerts)
        if policy.recipe is None:
            packet = self._apply_mode(
                policy.mode,
                self._select_standard_sections(policy, available, always_include_pending=bool(compiled.planned_checks())),
                ledger,
            )
        else:
            packet = self._apply_recipe(compiled, ledger, policy.recipe, available, policy.mode)
        packet = self._enforce_safety_sections(packet, available)
        packet = self._maybe_compress(packet, policy)
        if "context_recipe_realization" in packet:
            packet = self._finalize_recipe_realization(packet)
        return packet

    def _enforce_safety_sections(self, packet: dict[str, Any], available: dict[str, Any]) -> dict[str, Any]:
        out = dict(packet)
        out.setdefault("automatic_memory_available", True)
        for key in (
            "active_verifier_findings",
            "pending_checks",
            "automatic_memory_findings",
            "no_progress_controls",
            "action_constraints",
            "solver_parse_errors",
            "blocked_denied_receipts",
            "output_handles",
        ):
            if key in available and key not in out:
                out[key] = available[key]
        # The solver must always be able to see the output of commands it just
        # ran, regardless of architect context_policy/recipe choice. Without
        # this, the solver is told "produce X output" by an active finding
        # while the actual X output from the command it already ran is
        # invisible to it next step -- the harness discards the solver's own
        # working memory and then blames it for repeating the command.
        # Exception: if a recipe deliberately made command_results queryable-
        # not-inline (a size/token decision, not an omission), the solver can
        # still retrieve it on demand -- respect that explicit choice instead
        # of re-inlining the full payload and defeating the recipe's budget.
        if "command_results" in available and "command_results" not in out:
            realization = packet.get("context_recipe_realization")
            made_queryable = False
            if isinstance(realization, dict):
                made_queryable = any(
                    item.get("selector") == "command_results"
                    for item in realization.get("queryable_not_inline", []) or []
                )
            if not made_queryable:
                out["command_results"] = available["command_results"]
        return out

    def _available_sections(
        self,
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        alerts: list["MonitorAlert"],
    ) -> dict[str, Any]:
        packet: dict[str, Any] = {
            "open_obligations": [item.as_dict() for item in ledger.open_obligations()],
            "obligation_status": ledger.obligation_snapshot(),
            "monitor_alerts": [
                {
                    "code": alert.code,
                    "message": alert.message,
                    "severity": alert.severity,
                    "blocker_code": alert.blocker_code,
                    "recommend_reconfigure": alert.recommend_reconfigure,
                }
                for alert in alerts[: compiled.context_policy.max_alerts]
            ],
            "live_processes": ledger.live_processes(),
            "recent_progress": [
                {
                    "receipt_id": receipt.receipt_id,
                    "kind": receipt.kind,
                    "summary": receipt.summary,
                }
                for receipt in ledger.recent_progress(compiled.context_policy.max_recent_receipts)
            ],
            "failure_clusters": ledger.failure_clusters(compiled.context_policy.max_failure_clusters),
            "artifacts_present": sorted(ledger.current_artifacts()),
            "candidate_leaderboard": ledger.candidate_leaderboard(compiled.context_policy.max_candidates),
            "installed_capabilities": sorted(ledger.installed_capabilities),
            "planned_checks": [
                {
                    "check_id": check.check_id,
                    "label": check.label,
                    "command": check.command,
                    "origin": check.origin,
                }
                for check in compiled.planned_checks()
            ],
        }

        planned = compiled.planned_checks()
        latest = {outcome.check_id: outcome for outcome in ledger.latest_checks(compiled.check_plan_ids)}
        pending: list[dict[str, str | bool | None]] = []
        for check in planned[:16]:
            outcome = latest.get(check.check_id)
            passed: bool | None = outcome.passed if outcome is not None else None
            failure_kind = ""
            detail = ""
            if outcome is not None and not outcome.passed:
                failure_kind = outcome.blocker_code or "check_failed"
                detail = outcome.detail
            pending.append({
                "label": check.label,
                "command_short": check.command[:80],
                "passed": passed,
                "failure_kind": failure_kind,
                "repair_hint": _repair_hint(check.label, failure_kind, detail),
            })
        if pending:
            packet["pending_checks"] = pending

        repeated = ledger.repeated_actions()
        if repeated:
            packet["repeated_actions"] = repeated

        already_read = ledger.files_already_read()
        if already_read:
            packet["files_already_read"] = already_read

        latest_reads = self._latest_file_reads(ledger, limit=3)
        if latest_reads:
            packet["latest_file_reads"] = latest_reads

        command_results = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind == "run_command"
        ][-max(0, compiled.context_policy.max_recent_receipts):]
        packet["command_results"] = command_results

        memory_loop = self._memory_loop_feedback(ledger)
        if memory_loop:
            packet["memory_loop_feedback"] = memory_loop

        automatic_memory = self._automatic_memory_findings(ledger)
        if automatic_memory:
            packet["automatic_memory_findings"] = automatic_memory

        no_progress_controls = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind == "no_progress_control"
        ][-4:]
        if no_progress_controls:
            packet["no_progress_controls"] = no_progress_controls
            packet["action_constraints"] = self._action_constraints_from_no_progress(no_progress_controls)
        parse_errors = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind == "solver_parse_error"
        ][-4:]
        if parse_errors:
            packet["solver_parse_errors"] = parse_errors

        denied = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind in {"unsupported_solver_reconfigure", "action_validation", "safety_block", "unknown_action", "automatic_memory_block"}
        ][-8:]
        if denied:
            packet["blocked_denied_receipts"] = denied

        handles: list[dict[str, Any]] = []
        for receipt in ledger.all_receipts():
            payload = receipt.payload or {}
            if payload.get("stdout_handle"):
                handles.append({"handle": payload.get("stdout_handle"), "receipt_id": receipt.receipt_id, "stream": "stdout", "bytes": payload.get("stdout_bytes", 0)})
            if payload.get("stderr_handle"):
                handles.append({"handle": payload.get("stderr_handle"), "receipt_id": receipt.receipt_id, "stream": "stderr", "bytes": payload.get("stderr_bytes", 0)})
            if payload.get("file_handle"):
                handles.append({"handle": payload.get("file_handle"), "receipt_id": receipt.receipt_id, "stream": "file", "bytes": payload.get("bytes", 0), "path": payload.get("path", "")})
        if handles:
            packet["output_handles"] = handles[-16:]

        no_progress_streak = ledger.no_progress_streak()
        if no_progress_streak:
            packet["stuck"] = {
                "no_progress": no_progress_streak >= 3,
                "no_progress_streak": no_progress_streak,
            }

        active_findings = ledger.active_finding_context(len(ledger.all_receipts()))
        if active_findings:
            packet["active_verifier_findings"] = active_findings
        artifact_rows = artifact_history(ledger.all_receipts(), limit=12)
        if artifact_rows:
            packet["artifact_history"] = artifact_rows
        event_rows = memory_events(ledger.all_receipts(), limit=20)
        if event_rows:
            packet["memory_events"] = event_rows
        latest_failure = self._last_failures(ledger, 1)
        if latest_failure:
            packet["latest_failure"] = self._receipt_inline_view(latest_failure[-1])
        failed_checks = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind == "check_result" and not receipt.success
        ][-8:]
        if failed_checks:
            packet["failed_checks"] = failed_checks
        observations = [
            self._receipt_inline_view(receipt)
            for receipt in ledger.all_receipts()
            if receipt.kind == "record_observation" and receipt.success
        ][-8:]
        if observations:
            packet["observations"] = observations
        return packet

    def _select_standard_sections(
        self,
        policy: ContextPolicy,
        available: dict[str, Any],
        *,
        always_include_pending: bool,
    ) -> dict[str, Any]:
        packet: dict[str, Any] = {}
        for key in _STANDARD_SECTION_KEYS:
            if key in policy.include_sections:
                packet[key] = available[key]
        if "pending_checks" in available and (always_include_pending or "pending_checks" in policy.include_sections):
            packet["pending_checks"] = available["pending_checks"]
        for key in ("repeated_actions", "files_already_read", "latest_file_reads", "memory_loop_feedback", "automatic_memory_findings", "no_progress_controls", "action_constraints", "stuck", "active_verifier_findings"):
            if key in available:
                packet[key] = available[key]
        return packet

    def _apply_recipe(
        self,
        compiled: CompiledRuntime,
        ledger: ExecutionLedger,
        recipe: ContextRecipe,
        available: dict[str, Any],
        mode: str,
    ) -> dict[str, Any]:
        packet: dict[str, Any] = {"automatic_memory_available": True}
        if mode == "retrieval_augmented":
            packet["automatic_memory_guidance"] = (
                "Memory repeat interception is automatic. When prior evidence matches a proposed read, command, check, or overwrite, "
                "use that surfaced evidence, narrow the target, justify the repeat, or change strategy."
            )

        selected: list[dict[str, Any]] = []
        omitted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        queryable_not_inline: list[dict[str, Any]] = []

        for field_name in recipe.unsupported_fields:
            rejected.append({
                "field": field_name,
                "reason": "unsupported_recipe_field",
            })

        queryable_requested = tuple(dict.fromkeys(recipe.make_queryable_not_inline))
        exact_requested = tuple(dict.fromkeys(recipe.always_include + recipe.preserve_exact))
        exact_preserved = set(recipe.preserve_exact)
        queryable_requested_set = set(queryable_requested)
        selected_keys: set[str] = set()

        for selector in exact_requested:
            if selector not in _SUPPORTED_EXACT_RECIPE_SELECTORS:
                rejected.append({
                    "selector": selector,
                    "reason": "unsupported_selector",
                    "selector_type": "exact",
                })
                continue
            if selector in queryable_requested_set and selector not in exact_preserved:
                meta = self._queryable_section_meta(selector, available.get(selector))
                queryable_not_inline.append(meta)
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_not_inline",
                })
                continue
            if selector in queryable_requested_set and selector in exact_preserved:
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_request_overridden_by_preserve_exact",
                })
            if selector not in available:
                omitted.append({
                    "selector": selector,
                    "reason": "no_data",
                })
                continue
            packet[selector] = available[selector]
            selected_keys.add(selector)
            selected.append({
                "selector": selector,
                "section": selector,
                "item_count": _item_count(available[selector]),
                "preserved_exact": selector in exact_preserved,
            })

        for item in recipe.include_recent:
            selector = item.selector
            count = max(0, int(item.count))
            if selector not in _RECENT_RECIPE_SELECTORS:
                rejected.append({
                    "selector": selector,
                    "reason": "unsupported_selector",
                    "selector_type": "recent",
                    "requested_count": count,
                })
                continue
            if count <= 0:
                omitted.append({
                    "selector": selector,
                    "reason": "nonpositive_count",
                    "requested_count": count,
                })
                continue
            receipts = self._recent_receipts(selector, ledger, count)
            if selector in queryable_requested_set:
                queryable_not_inline.append(self._queryable_receipt_meta(selector, receipts, count))
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_not_inline",
                    "requested_count": count,
                    "matching_count": len(receipts),
                })
                continue
            if not receipts:
                omitted.append({
                    "selector": selector,
                    "reason": "no_matching_receipts",
                    "requested_count": count,
                })
                continue
            packet[selector] = [self._receipt_inline_view(receipt) for receipt in receipts]
            selected_keys.add(selector)
            selected.append({
                "selector": selector,
                "section": selector,
                "requested_count": count,
                "included_count": len(receipts),
                "receipt_ids": [receipt.receipt_id for receipt in receipts],
            })

        if recipe.include_last_failure > 0:
            failures = self._last_failures(ledger, recipe.include_last_failure)
            selector = "last_failures"
            if selector in queryable_requested_set:
                queryable_not_inline.append(self._queryable_receipt_meta(selector, failures, recipe.include_last_failure))
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_not_inline",
                    "requested_count": recipe.include_last_failure,
                    "matching_count": len(failures),
                })
            elif failures:
                packet[selector] = [self._receipt_inline_view(receipt) for receipt in failures]
                selected.append({
                    "selector": selector,
                    "section": selector,
                    "requested_count": recipe.include_last_failure,
                    "included_count": len(failures),
                    "receipt_ids": [receipt.receipt_id for receipt in failures],
                })
                selected_keys.add(selector)
            else:
                omitted.append({
                    "selector": selector,
                    "reason": "no_matching_receipts",
                    "requested_count": recipe.include_last_failure,
                })

        for selector in queryable_requested:
            if selector in selected_keys:
                continue
            if any(item.get("selector") == selector for item in queryable_not_inline):
                continue
            if (
                selector not in _SUPPORTED_EXACT_RECIPE_SELECTORS
                and selector not in _RECENT_RECIPE_SELECTORS
                and selector != "last_failures"
            ):
                if not any(item.get("selector") == selector for item in rejected):
                    rejected.append({
                        "selector": selector,
                        "reason": "unsupported_selector",
                        "selector_type": "queryable_not_inline",
                    })
                continue
            if selector in _SUPPORTED_EXACT_RECIPE_SELECTORS:
                queryable_not_inline.append(self._queryable_section_meta(selector, available.get(selector)))
            elif selector in _RECENT_RECIPE_SELECTORS:
                queryable_not_inline.append(
                    self._queryable_receipt_meta(
                        selector,
                        self._recent_receipts(selector, ledger, len(ledger.all_receipts())),
                        0,
                    )
                )
            elif selector == "last_failures":
                queryable_not_inline.append(
                    self._queryable_receipt_meta(
                        selector,
                        self._last_failures(ledger, len(ledger.all_receipts())),
                        0,
                    )
                )
            if not any(item.get("selector") == selector for item in queryable_not_inline):
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_not_inline_unselected",
                })
            else:
                omitted.append({
                    "selector": selector,
                    "reason": "queryable_not_inline",
                })

        realization = {
            "enabled": True,
            "mode_fallback": mode,
            "declared": {
                "always_include": list(recipe.always_include),
                "include_recent": [
                    {"selector": item.selector, "count": int(item.count)}
                    for item in recipe.include_recent
                ],
                "include_last_failure": int(recipe.include_last_failure),
                "preserve_exact": list(recipe.preserve_exact),
                "make_queryable_not_inline": list(recipe.make_queryable_not_inline),
                "unsupported_fields": list(recipe.unsupported_fields),
            },
            "selected": selected,
            "omitted": omitted,
            "rejected": rejected,
            "queryable_not_inline": queryable_not_inline,
            "counts": {
                "selected": len(selected),
                "omitted": len(omitted),
                "rejected": len(rejected),
                "queryable_not_inline": len(queryable_not_inline),
            },
        }
        packet["context_recipe_realization"] = realization
        return packet

    def _apply_mode(self, mode: str, packet: dict[str, Any], ledger: ExecutionLedger) -> dict[str, Any]:
        if mode == "default_bounded":
            return packet
        if mode == "retrieval_augmented":
            enriched = dict(packet)
            enriched["automatic_memory_available"] = True
            enriched["automatic_memory_guidance"] = (
                "Memory repeat interception is automatic. When prior evidence matches a proposed read, command, check, or overwrite, "
                "use that surfaced evidence, narrow the target, justify the repeat, or change strategy."
            )
            return enriched
        if mode == "latest_tool_result_only":
            latest = self._latest_tool_receipt(ledger)
            result = {"automatic_memory_available": True}
            if latest:
                result["latest_tool_result"] = latest
            for key in ("pending_checks", "active_verifier_findings", "no_progress_controls", "action_constraints", "stuck"):
                if key in packet:
                    result[key] = packet[key]
            return result
        if mode == "rolling_recent":
            return {
                "recent_progress": packet.get("recent_progress", []),
                "pending_checks": packet.get("pending_checks", []),
                "artifacts_present": packet.get("artifacts_present", []),
                "active_verifier_findings": packet.get("active_verifier_findings", []),
                "automatic_memory_available": True,
            }
        if mode == "failure_focused":
            keys = (
                "active_verifier_findings",
                "pending_checks",
                "failure_clusters",
                "repeated_actions",
                "files_already_read",
                "no_progress_controls",
                "action_constraints",
                "stuck",
            )
            return {key: packet[key] for key in keys if key in packet} | {"automatic_memory_available": True}
        return packet

    def _recent_receipts(self, selector: str, ledger: ExecutionLedger, count: int) -> list[Receipt]:
        receipts = list(ledger.all_receipts())
        if selector == "recent_progress":
            matches = [
                receipt
                for receipt in receipts
                if receipt.state_change
                or (receipt.kind == "check_result" and receipt.success)
                or (receipt.kind == "schema_validation" and receipt.success)
            ]
        elif selector == "tool_results":
            matches = [receipt for receipt in receipts if receipt.kind in _TOOL_RESULT_KINDS]
        elif selector == "file_reads":
            matches = [receipt for receipt in receipts if receipt.kind == "read_file"]
        elif selector == "file_writes":
            matches = [receipt for receipt in receipts if receipt.kind == "write_file"]
        elif selector == "command_results":
            matches = [receipt for receipt in receipts if receipt.kind == "run_command"]
        elif selector == "check_results":
            matches = [receipt for receipt in receipts if receipt.kind == "check_result"]
        elif selector == "query_memory_results":
            matches = [receipt for receipt in receipts if receipt.kind == "query_memory"]
        elif selector == "verifier_results":
            matches = [receipt for receipt in receipts if receipt.kind == "model_verifier_result"]
        elif selector == "artifact_history":
            matches = [receipt for receipt in receipts if artifact_history((receipt,), limit=1)]
        elif selector == "observations":
            matches = [receipt for receipt in receipts if receipt.kind == "record_observation"]
        else:
            matches = []
        return matches[-count:]

    def _last_failures(self, ledger: ExecutionLedger, count: int) -> list[Receipt]:
        failures = [receipt for receipt in ledger.all_receipts() if not receipt.success]
        return failures[-count:]

    @staticmethod
    def _latest_tool_receipt(ledger: ExecutionLedger) -> dict[str, Any] | None:
        tool_kinds = {"read_file", "write_file", "run_command", "query_memory", "check_result", "schema_validation"}
        for receipt in reversed(ledger.all_receipts()):
            if receipt.kind in tool_kinds:
                return {
                    "receipt_id": receipt.receipt_id,
                    "step": receipt.step,
                    "kind": receipt.kind,
                    "success": receipt.success,
                    "summary": receipt.summary,
                    "failure_class": receipt.failure_class,
                }
        return None

    def _queryable_section_meta(self, selector: str, value: Any) -> dict[str, Any]:
        return {
            "selector": selector,
            "section": selector,
            "item_count": _item_count(value),
            "access": "query_memory",
            "reason": "recipe_make_queryable_not_inline",
        }

    def _queryable_receipt_meta(self, selector: str, receipts: list[Receipt], requested_count: int) -> dict[str, Any]:
        return {
            "selector": selector,
            "section": selector,
            "requested_count": requested_count,
            "matching_count": len(receipts),
            "receipt_ids": [receipt.receipt_id for receipt in receipts],
            "access": "query_memory",
            "reason": "recipe_make_queryable_not_inline",
        }

    def _receipt_inline_view(self, receipt: Receipt) -> dict[str, Any]:
        row: dict[str, Any] = {
            "receipt_id": receipt.receipt_id,
            "step": receipt.step,
            "kind": receipt.kind,
            "success": receipt.success,
            "summary": receipt.summary,
        }
        if receipt.failure_class:
            row["failure_class"] = receipt.failure_class
        payload = receipt.payload
        for key in ("path", "command", "check_id", "exit_code", "bytes", "query", "detail", "blocker_code", "stdout_handle", "stderr_handle", "file_handle", "offset", "span"):
            value = payload.get(key)
            if value not in (None, "", (), [], {}):
                row[key] = value
        if receipt.kind == "read_file" and payload.get("excerpt"):
            row["excerpt"] = str(payload["excerpt"])
        if receipt.kind == "run_command":
            stdout = str(payload.get("stdout", ""))
            stderr = str(payload.get("stderr", ""))
            if stdout:
                row["stdout"] = stdout
            if stderr:
                row["stderr"] = stderr
        if receipt.kind in {"read_output", "grep_output", "read_file_page"}:
            chunk = str(payload.get("chunk", ""))
            if chunk:
                row["chunk"] = chunk
        if receipt.kind == "query_memory":
            results = payload.get("results", [])
            if isinstance(results, list):
                row["result_count"] = len(results)
            for key in ("no_new_evidence", "guidance"):
                value = payload.get(key)
                if value not in (None, "", (), [], {}):
                    row[key] = value
        if receipt.kind == "no_progress_control":
            for key in ("consequence", "target", "action_family", "repeat_count"):
                value = payload.get(key)
                if value not in (None, "", (), [], {}):
                    row[key] = value
        return row

    def _latest_file_reads(self, ledger: ExecutionLedger, limit: int = 3) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for receipt in ledger.all_receipts():
            if receipt.kind != "read_file" or not receipt.success:
                continue
            payload = receipt.payload or {}
            row = {
                "receipt_id": receipt.receipt_id,
                "step": receipt.step,
                "path": payload.get("path", ""),
                "content_hash": payload.get("content_hash", ""),
                "bytes": payload.get("bytes", 0),
                "excerpt": payload.get("excerpt", ""),
            }
            rows.append({k: v for k, v in row.items() if v not in (None, "", (), [], {})})
        return rows[-max(0, limit):]

    def _memory_loop_feedback(self, ledger: ExecutionLedger) -> dict[str, Any] | None:
        queries = [r for r in ledger.all_receipts() if r.kind == "query_memory"]
        if len(queries) < 2:
            return None
        recent = queries[-3:]
        empty_or_same = []
        for receipt in recent:
            payload = receipt.payload or {}
            results = payload.get("results", [])
            empty_or_same.append(len(results) == 0 or bool(payload.get("no_new_evidence")))
        if len(recent) >= 2 and all(empty_or_same[-2:]):
            return {
                "repeated_memory_queries": len(recent),
                "latest_query": str((recent[-1].payload or {}).get("query", "")),
                "guidance": (
                    "Repeated query_memory calls produced no new evidence. Act on existing file/check evidence, "
                    "inspect a concrete file, write/repair the artifact, or request missing capability; do not keep querying memory."
                ),
                "recent_receipt_ids": [r.receipt_id for r in recent],
            }
        return None

    @staticmethod
    def _automatic_memory_findings(ledger: ExecutionLedger, limit: int = 4) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for receipt in ledger.all_receipts():
            if receipt.kind != "automatic_memory" or not receipt.success:
                continue
            payload = receipt.payload or {}
            rows.append({
                "receipt_id": receipt.receipt_id,
                "step": receipt.step,
                "summary": receipt.summary,
                "action_kind": payload.get("action_kind"),
                "target": payload.get("target"),
                "match_count": payload.get("match_count"),
                "latest_receipt_id": payload.get("latest_receipt_id"),
                "same_content_hash": payload.get("same_content_hash"),
                "repeat_justified": payload.get("repeat_justified"),
                "guidance": payload.get("guidance"),
                "recent_evidence": payload.get("recent_evidence", [])[:2],
            })
        return rows[-max(0, limit):]

    @staticmethod
    def _action_constraints_from_no_progress(no_progress_controls: list[dict[str, Any]]) -> dict[str, Any]:
        latest = no_progress_controls[-1]
        payload = latest.get("payload") if isinstance(latest.get("payload"), dict) else {}
        target = str(payload.get("target", latest.get("target", ""))).strip()
        consequence = str(payload.get("consequence", latest.get("consequence", ""))).strip()
        action_family = payload.get("action_family", latest.get("action_family", "evidence_display_command"))
        return {
            "source": "no_progress_control",
            "consequence": consequence or "soft_block",
            "blocked_action_family": action_family,
            "blocked_target": target,
            "do_not_repeat": [
                {
                    "action_family": action_family,
                    "target": target,
                }
            ],
            "allowed_next_action_families": [
                "repair_or_write_artifact",
                "execute_or_semantically_validate_artifact",
                "inspect_new_target",
                "declare_concrete_blocker",
            ],
            "message": (
                "The runtime already blocked repeated evidence display. The next action must repair the artifact, "
                "execute or semantically validate it, inspect a different target, or declare a concrete blocker."
            ),
        }

    @staticmethod
    def _maybe_compress(packet: dict[str, Any], policy: Any) -> dict[str, Any]:
        budget = int(policy.model_context_window_tokens * policy.compression_trigger_ratio)
        estimated_tokens = max(1, len(json.dumps(packet, sort_keys=True, default=str)) // 4)
        if estimated_tokens <= budget:
            return packet
        compressed = dict(packet)
        preserved_exact = {"active_verifier_findings", "pending_checks", "no_progress_controls", "action_constraints", "stuck", "command_results", "latest_file_reads", "solver_parse_errors", "blocked_denied_receipts", "output_handles"}
        recipe = getattr(policy, "recipe", None)
        if recipe is not None:
            preserved_exact.update(str(item) for item in recipe.preserve_exact)
        for key in ("recent_progress", "failure_clusters", "candidate_leaderboard"):
            if key in preserved_exact:
                continue
            if isinstance(compressed.get(key), list):
                original = compressed[key]
                compressed[key] = original[-3:]
                compressed[f"{key}_compressed"] = {"original_count": len(original), "kept_last": len(compressed[key])}
        compressed["context_compression"] = {
            "triggered": True,
            "estimated_tokens_before": estimated_tokens,
            "budget_tokens": budget,
            "threshold_ratio": policy.compression_trigger_ratio,
            "preserved_exact": sorted(preserved_exact),
        }
        return compressed

    def _finalize_recipe_realization(self, packet: dict[str, Any]) -> dict[str, Any]:
        body = {key: value for key, value in packet.items() if key != "context_recipe_realization"}
        realization = dict(packet["context_recipe_realization"])
        counts = dict(realization.get("counts", {}))
        counts["rendered_sections"] = len(body)
        counts["nonempty_sections"] = sum(1 for value in body.values() if _item_count(value) > 0)
        realization["counts"] = counts
        realization["rendered_section_counts"] = {
            key: _item_count(value)
            for key, value in sorted(body.items())
        }
        byte_count = len(stable_json(body).encode("utf-8"))
        realization["byte_count_v1"] = byte_count
        realization["token_estimate_v1"] = max(1, (byte_count + 3) // 4)
        finalized = dict(packet)
        finalized["context_recipe_realization"] = realization
        return finalized


def _item_count(value: Any) -> int:
    if isinstance(value, (list, tuple, dict, set)):
        return len(value)
    if value in (None, "", False):
        return 0
    return 1


def _repair_hint(label: str, failure_kind: str, detail: str) -> str:
    if not failure_kind:
        return ""
    if failure_kind == "check_broken":
        return "Do not retry this check command; treat it as invalid check evidence and continue fixing the task artifact."
    if label.startswith("exists:"):
        target = label.split(":", 1)[1]
        return f"Create or write the required artifact at {target}; do not just rerun the existence check."
    if label.startswith("schema:"):
        target = label.split(":", 1)[1]
        if target.lower().endswith(".csv"):
            return f"Update {target} so its CSV header contains the required columns."
        return f"Update {target} so the structured output contains the required keys."
    if label.startswith("size:"):
        target = label.split(":", 1)[1]
        return f"Adjust {target} to satisfy the file-size threshold."
    if detail:
        return "Use the failure detail to change the artifact; avoid repeating the same verification action."
    return "Change the artifact or strategy before rechecking."
