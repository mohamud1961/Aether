from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .ingest import HarnessRunView, open_harness_run_view


LAYER_ORDER: Tuple[str, ...] = (
    "POLICY",
    "SYSTEM",
    "CONTRACTS",
    "TASK",
    "EVIDENCE",
    "STATE",
    "SCRATCH",
)


def dump_context_diagnostics(
    run_dir: str | Path,
    *,
    max_steps: int = 5,
    out_dir: str | Path | None = None,
) -> Dict[str, Any]:
    if max_steps < 1:
        raise ValueError("max_steps must be >= 1")

    view = open_harness_run_view(run_dir)
    events = view.load_events()
    target_steps = _first_n_step_ids(events, max_steps)
    compiled_by_step = _latest_compiler_event_by_step(events, target_steps)

    step_diagnostics: List[Dict[str, Any]] = []
    for step_id in target_steps:
        compiler_event = compiled_by_step.get(step_id)
        if compiler_event is None:
            step_diagnostics.append(
                {
                    "step_id": step_id,
                    "has_compiled_context": False,
                    "reason": "no_compiler_event_for_step",
                    "layer_order": list(LAYER_ORDER),
                    "layers": [],
                    "truncation_flags": ["NONE"],
                    "sweet_zone_pct": None,
                    "completion_contract_digest_present": False,
                }
            )
            continue

        step_diagnostics.append(_diagnose_compiler_event(view, compiler_event))

    run_id = _single_run_id(events)
    diagnostic = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": view.run_dir.as_posix(),
        "run_id": run_id,
        "steps_requested": max_steps,
        "steps_analyzed": len(target_steps),
        "layer_order": list(LAYER_ORDER),
        "steps": step_diagnostics,
    }

    output_root = Path(out_dir) if out_dir is not None else view.run_dir
    output_root.mkdir(parents=True, exist_ok=True)

    text_path = output_root / "debug_context.txt"
    json_path = output_root / "context_diagnostic.json"

    text_path.write_text(_render_debug_context(diagnostic), encoding="utf-8")
    json_path.write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "debug_context_path": text_path.as_posix(),
        "context_diagnostic_path": json_path.as_posix(),
        "steps_analyzed": len(target_steps),
    }


def _first_n_step_ids(events: Sequence[Any], max_steps: int) -> List[int]:
    seen: set[int] = set()
    ordered: List[int] = []
    for event in events:
        step_id = getattr(event, "step_id", -1)
        if not isinstance(step_id, int) or step_id < 0:
            continue
        if step_id in seen:
            continue
        seen.add(step_id)
        ordered.append(step_id)
        if len(ordered) >= max_steps:
            break
    return ordered


def _latest_compiler_event_by_step(events: Sequence[Any], target_steps: Sequence[int]) -> Dict[int, Any]:
    target = set(target_steps)
    by_step: Dict[int, Any] = {}
    for event in events:
        step_id = getattr(event, "step_id", -1)
        if not isinstance(step_id, int) or step_id not in target:
            continue
        if getattr(event, "event_type", None) != "CONTEXTPACK_COMPILED":
            continue
        by_step[step_id] = event
    return by_step


def _diagnose_compiler_event(view: HarnessRunView, compiler_event: Any) -> Dict[str, Any]:
    payload = getattr(compiler_event, "payload", {})
    artifact_refs = payload.get("artifact_refs") if isinstance(payload.get("artifact_refs"), list) else []

    context_pack_ref = _first_non_empty(
        payload.get("context_pack_ref"),
        payload.get("context_pack_hash"),
        artifact_refs[0] if len(artifact_refs) >= 1 else None,
    )
    manifest_ref = _first_non_empty(
        payload.get("manifest_ref"),
        payload.get("manifest_hash"),
        artifact_refs[1] if len(artifact_refs) >= 2 else None,
    )

    context_pack = _load_json_object(view, context_pack_ref)
    manifest = _load_json_object(view, manifest_ref)

    layers, aggregated_flags, completion_contract_present = _analyze_layers(context_pack)
    if not aggregated_flags:
        aggregated_flags = _manifest_truncation_flags(manifest)
    if not aggregated_flags:
        aggregated_flags = {"NONE"}

    sweet_zone_pct = payload.get("sweet_zone_pct")
    if not isinstance(sweet_zone_pct, (int, float)):
        sweet_zone_pct = manifest.get("sweet_zone_pct")
    if isinstance(sweet_zone_pct, int):
        sweet_zone_pct = float(sweet_zone_pct)
    if not isinstance(sweet_zone_pct, float):
        sweet_zone_pct = None

    return {
        "step_id": payload.get("step_id"),
        "has_compiled_context": True,
        "compile_event_id": payload.get("event_id"),
        "context_pack_ref": context_pack_ref,
        "manifest_ref": manifest_ref,
        "context_pack_hash": payload.get("context_pack_hash"),
        "manifest_hash": payload.get("manifest_hash"),
        "layer_order": list(LAYER_ORDER),
        "layers": layers,
        "truncation_flags": sorted(aggregated_flags),
        "sweet_zone_pct": sweet_zone_pct,
        "completion_contract_digest_present": completion_contract_present,
    }


def _load_json_object(view: HarnessRunView, artifact_id: Optional[str]) -> Dict[str, Any]:
    if not isinstance(artifact_id, str) or not artifact_id:
        return {}
    try:
        payload = view.artifact_store.load_json(artifact_id)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _analyze_layers(context_pack: Mapping[str, Any]) -> tuple[List[Dict[str, Any]], set[str], bool]:
    layers: List[Dict[str, Any]] = []
    aggregated_flags: set[str] = set()
    completion_contract_present = False

    for layer_name in LAYER_ORDER:
        raw_items = context_pack.get(layer_name)
        if not isinstance(raw_items, list):
            raw_items = []

        trusted_count = 0
        untrusted_count = 0
        item_diagnostics: List[Dict[str, Any]] = []
        for index, raw_item in enumerate(raw_items):
            item = raw_item if isinstance(raw_item, dict) else {"content": raw_item}
            trust_tag = _trust_tag(item)
            if trust_tag == "UNTRUSTED":
                untrusted_count += 1
            else:
                trusted_count += 1

            source_ref = item.get("source_ref")
            if _is_completion_contract_digest_item(item):
                completion_contract_present = True

            item_flags = _item_truncation_flags(item)
            aggregated_flags.update(item_flags)
            item_diagnostics.append(
                {
                    "index": index,
                    "trust_tag": trust_tag,
                    "source_ref": source_ref,
                    "kind": item.get("kind"),
                    "truncation_flags": sorted(item_flags) if item_flags else [],
                }
            )

        layers.append(
            {
                "name": layer_name,
                "item_count": len(raw_items),
                "trusted_count": trusted_count,
                "untrusted_count": untrusted_count,
                "items": item_diagnostics,
            }
        )

    if not completion_contract_present:
        completion_contract_present = _find_completion_contract_digest_anywhere(context_pack)

    return layers, aggregated_flags, completion_contract_present


def _trust_tag(item: Mapping[str, Any]) -> str:
    trust_level = str(item.get("trust_level", "")).upper()
    if trust_level == "UNTRUSTED":
        return "UNTRUSTED"
    authority_tier = str(item.get("authority_tier", "")).lower()
    if authority_tier == "untrusted":
        return "UNTRUSTED"
    return "trusted"


def _item_truncation_flags(item: Mapping[str, Any]) -> set[str]:
    flags: set[str] = set()

    raw_flags = item.get("truncation_flags")
    if isinstance(raw_flags, str) and raw_flags:
        flags.add(raw_flags)
    elif isinstance(raw_flags, list):
        for value in raw_flags:
            if isinstance(value, str) and value:
                flags.add(value)

    truncation = item.get("truncation")
    if isinstance(truncation, dict):
        for stream in ("stdout", "stderr"):
            stream_meta = truncation.get(stream)
            if not isinstance(stream_meta, dict):
                continue
            if stream_meta.get("unknown") is True:
                flags.add(f"{stream.upper()}_UNKNOWN")
            if stream_meta.get("truncated") is True:
                flags.add(f"{stream.upper()}_TRUNCATED")
    return flags


def _manifest_truncation_flags(manifest: Mapping[str, Any]) -> set[str]:
    flags: set[str] = set()
    reasons = manifest.get("reasons")
    if isinstance(reasons, list):
        for reason in reasons:
            if not isinstance(reason, str):
                continue
            if "trunc" in reason.lower():
                flags.add(reason)
    return flags


def _find_completion_contract_digest_anywhere(context_pack: Mapping[str, Any]) -> bool:
    for value in context_pack.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if _is_completion_contract_digest_item(item):
                return True
    return False


def _is_completion_contract_digest_item(item: Mapping[str, Any]) -> bool:
    kind = item.get("kind")
    if isinstance(kind, str) and kind == "completion_contract_digest":
        return True
    source_ref = item.get("source_ref")
    if isinstance(source_ref, str) and (
        source_ref == "completion_contract_digest"
        or source_ref.endswith("/completion_contract_digest")
    ):
        return True
    return False


def _single_run_id(events: Iterable[Any]) -> Optional[str]:
    run_ids = sorted(
        {
            run_id
            for run_id in (getattr(event, "payload", {}).get("run_id") for event in events)
            if isinstance(run_id, str) and run_id
        }
    )
    if not run_ids:
        return None
    if len(run_ids) == 1:
        return run_ids[0]
    return ",".join(run_ids)


def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def _render_debug_context(payload: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("Context Compiler Diagnostic")
    lines.append(f"run_dir: {payload.get('run_dir')}")
    lines.append(f"run_id: {payload.get('run_id')}")
    lines.append(f"generated_at: {payload.get('generated_at')}")
    lines.append(f"steps_requested: {payload.get('steps_requested')}")
    lines.append(f"steps_analyzed: {payload.get('steps_analyzed')}")
    lines.append("")

    for step in payload.get("steps", []):
        lines.append(f"Step {step.get('step_id')}")
        lines.append(f"  has_compiled_context: {step.get('has_compiled_context')}")
        if not step.get("has_compiled_context"):
            lines.append(f"  reason: {step.get('reason')}")
            lines.append("")
            continue
        lines.append(f"  compile_event_id: {step.get('compile_event_id')}")
        lines.append(f"  context_pack_ref: {step.get('context_pack_ref')}")
        lines.append(f"  manifest_ref: {step.get('manifest_ref')}")
        lines.append(f"  sweet_zone_pct: {step.get('sweet_zone_pct')}")
        lines.append(f"  truncation_flags: {', '.join(step.get('truncation_flags', []))}")
        lines.append(
            f"  completion_contract_digest_present: {step.get('completion_contract_digest_present')}"
        )
        lines.append(f"  layer_order: {' > '.join(step.get('layer_order', []))}")

        for layer in step.get("layers", []):
            lines.append(
                f"  Layer {layer.get('name')}: items={layer.get('item_count')} "
                f"trusted={layer.get('trusted_count')} untrusted={layer.get('untrusted_count')}"
            )
            for item in layer.get("items", []):
                trunc_flags = item.get("truncation_flags") or []
                trunc_text = ",".join(trunc_flags) if trunc_flags else "NONE"
                lines.append(
                    "    - [{trust}] source_ref={source_ref} kind={kind} truncation_flags={flags}".format(
                        trust=item.get("trust_tag"),
                        source_ref=item.get("source_ref"),
                        kind=item.get("kind"),
                        flags=trunc_text,
                    )
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
