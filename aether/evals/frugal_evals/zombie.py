from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from aether.evals.utils.events import Event, canonicalize_event_type
from aether.evals.utils.hashes import canonical_json_dumps, stable_hash
from aether.artifact_store import ArtifactStore
from aether.context_pack import ContextPackProjection
from aether.event_log import EventLog
from aether.model_adapter import ModelAdapter, ModelRequest, ModelResponse, NormalizedToolCall

from .ingest import open_harness_run_view

MODE_REPLAY_DECISION = "REPLAY_DECISION"

ACT_TOOL = "ACT_TOOL"
ACT_VERIFY = "ACT_VERIFY"
ACT_PLAN_UPDATE = "ACT_PLAN_UPDATE"
ACT_REANCHOR = "ACT_REANCHOR"
ACT_REFUSE = "ACT_REFUSE"

ACTION_SHAPES = (ACT_TOOL, ACT_VERIFY, ACT_PLAN_UPDATE, ACT_REANCHOR, ACT_REFUSE)
PHASES = ("Orient", "Explore", "Implement", "Verify")
VALID_ACTIONS_BY_PHASE: Dict[str, set[str]] = {
    "Orient": {ACT_TOOL, ACT_PLAN_UPDATE},
    "Explore": {ACT_TOOL, ACT_PLAN_UPDATE},
    "Implement": {ACT_TOOL, ACT_VERIFY, ACT_PLAN_UPDATE},
    "Verify": {ACT_VERIFY, ACT_TOOL, ACT_REANCHOR},
}

DEFAULT_PRICING_CONFIG: Dict[str, Any] = {
    "schema_version": "frugal_model_pricing.v1",
    "models": {
        "mock-zombie-v1": {
            "input_per_1m_tokens_usd": 0.0,
            "output_per_1m_tokens_usd": 0.0,
        },
        "claude-3-5-haiku-20241022": {
            "input_per_1m_tokens_usd": 0.80,
            "output_per_1m_tokens_usd": 4.00,
        },
        "gemini-2.0-flash": {
            "input_per_1m_tokens_usd": 0.10,
            "output_per_1m_tokens_usd": 0.40,
        },
    },
}


class ZombieRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class EpisodeRecord:
    episode_id: str
    run_id: str
    step_id: int
    run_dir: str
    source_event_id: str
    context_pack_ref: str
    model_request_ref: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EpisodeRecord":
        return cls(
            episode_id=_required_str(payload, "episode_id"),
            run_id=_required_str(payload, "run_id"),
            step_id=_required_int(payload, "step_id"),
            run_dir=_required_str(payload, "run_dir"),
            source_event_id=_required_str(payload, "source_event_id"),
            context_pack_ref=_required_str(payload, "context_pack_ref"),
            model_request_ref=_required_str(payload, "model_request_ref"),
        )


@dataclass(frozen=True)
class ZombieEpisodeResult:
    zombie_run_id: str
    run_dir: Path
    summary: Dict[str, Any]


class LocalMockZombieAdapter(ModelAdapter):
    def __init__(self, model_id: str = "mock-zombie-v1") -> None:
        self._model_id = model_id

    def get_model_identifier(self) -> str:
        return self._model_id

    def format_context(self, context_pack: ContextPackProjection) -> ModelRequest:
        doctrine_items = context_pack.get_tier_items("DOCTRINE")
        conversation_items = context_pack.get_tier_items("CONVERSATION")

        system_prompt = "\n\n".join(
            str(item.get("content", "")) for item in doctrine_items if isinstance(item.get("content"), str)
        )
        messages: List[Dict[str, Any]] = []
        for item in conversation_items:
            role = item.get("role") if isinstance(item.get("role"), str) else "user"
            content = item.get("content") if isinstance(item.get("content"), str) else ""
            messages.append({"role": role, "content": content})

        return ModelRequest(
            system_prompt=system_prompt,
            messages=messages,
            tools=[
                {
                    "name": "run",
                    "description": "Execute a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                        "required": ["command"],
                    },
                }
            ],
            model_identifier=self._model_id,
            max_tokens=512,
            temperature=0.0,
        )

    def invoke(self, request: ModelRequest) -> ModelResponse:
        selector = int(request.request_hash[:2], 16) % len(ACTION_SHAPES)
        shape = ACTION_SHAPES[selector]

        tool_calls: List[NormalizedToolCall] = []
        finish_reason = "end_turn"
        text_content = ""

        if shape == ACT_TOOL:
            finish_reason = "tool_use"
            tool_args = {"command": ["ls", "-la"]}
            tool_calls.append(
                NormalizedToolCall(
                    tool_name="run",
                    tool_args=tool_args,
                    call_id=stable_hash({"name": "run", "args": tool_args, "index": 0})[:16],
                    index=0,
                )
            )
            text_content = "I will inspect files first."
        elif shape == ACT_VERIFY:
            text_content = "Run tests to verify the current state."
        elif shape == ACT_PLAN_UPDATE:
            text_content = "Update the plan to reflect new findings."
        elif shape == ACT_REANCHOR:
            text_content = "Reanchor: reset assumptions and summarize next checks."
        else:
            text_content = "I cannot safely proceed with this request."

        usage = {
            "input_tokens": max(1, len(request.request_bytes) // 4),
            "output_tokens": max(1, len(text_content.encode("utf-8")) // 4),
        }

        raw_payload = {
            "finish_reason": finish_reason,
            "text_content": text_content,
            "tool_calls": [
                {
                    "tool_name": call.tool_name,
                    "tool_args": call.tool_args,
                    "call_id": call.call_id,
                    "index": call.index,
                }
                for call in tool_calls
            ],
            "usage": usage,
        }
        raw_bytes = canonical_json_dumps(raw_payload).encode("utf-8")
        return ModelResponse(
            raw_bytes=raw_bytes,
            raw_hash=stable_hash(raw_payload),
            tool_calls=tool_calls,
            text_content=text_content,
            finish_reason=finish_reason,
            usage=usage,
            candidate_count=1,
            normalization_warnings=[],
        )


def parse_action_shape_from_response(response: ModelResponse) -> str:
    finish_reason = (response.finish_reason or "").lower()
    if response.tool_calls or "tool" in finish_reason:
        return ACT_TOOL

    text = (response.text_content or "").lower()
    if not text:
        return ACT_REFUSE

    if _contains_any(text, ("reanchor", "re-anchor", "reset assumptions", "revisit hypothesis")):
        return ACT_REANCHOR
    if _contains_any(text, ("verify", "verification", "run tests", "unit test", "validate", "assert")):
        return ACT_VERIFY
    if _contains_any(text, ("plan update", "update plan", "plan", "next steps", "roadmap")):
        return ACT_PLAN_UPDATE
    if _contains_any(text, ("cannot", "can't", "unable", "refuse", "won't", "do not have enough")):
        return ACT_REFUSE
    return ACT_REFUSE


def run_zombie_batch(
    *,
    episodes_path: str | Path,
    out_root: str | Path,
    model_id: str,
    adapter_mode: str = "mock",
    limit: Optional[int] = None,
    offset: int = 0,
    pricing_path: str | Path | None = None,
) -> Dict[str, Any]:
    if offset < 0:
        raise ZombieRunError("offset must be >= 0")
    if limit is not None and limit < 1:
        raise ZombieRunError("limit must be >= 1 when provided")

    pricing_file = Path(pricing_path) if pricing_path is not None else Path(__file__).with_name("model_pricing.json")
    pricing = _load_or_init_pricing(pricing_file)
    adapter = _build_adapter(adapter_mode=adapter_mode, model_id=model_id)

    episodes = _load_episodes(episodes_path)
    selected = episodes[offset:]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise ZombieRunError("No episodes selected for zombie batch")

    out_root_path = Path(out_root)
    out_root_path.mkdir(parents=True, exist_ok=True)

    batch_id = _new_batch_id(model_id=model_id)
    batch_dir = out_root_path / batch_id
    batch_dir.mkdir(parents=True, exist_ok=False)

    results: List[ZombieEpisodeResult] = []
    for episode in selected:
        results.append(
            _run_single_episode(
                episode=episode,
                adapter=adapter,
                model_id=model_id,
                pricing=pricing,
                batch_id=batch_id,
                batch_dir=batch_dir,
            )
        )

    batch_summary = _build_batch_summary(results=results, batch_id=batch_id, model_id=model_id)
    _verify_batch_outputs(results=results, batch_summary=batch_summary)

    batch_summary_path = batch_dir / "batch_summary.json"
    batch_summary_path.write_text(canonical_json_dumps(batch_summary) + "\n", encoding="utf-8")

    return {
        "batch_id": batch_id,
        "batch_dir": batch_dir.as_posix(),
        "batch_summary_path": batch_summary_path.as_posix(),
        "episode_count": len(results),
    }


def _run_single_episode(
    *,
    episode: EpisodeRecord,
    adapter: ModelAdapter,
    model_id: str,
    pricing: Mapping[str, Any],
    batch_id: str,
    batch_dir: Path,
) -> ZombieEpisodeResult:
    source_view = open_harness_run_view(episode.run_dir)
    source_events = _load_source_events(source_view.events_path)

    phase_at_episode = _phase_at_episode(source_events, source_event_id=episode.source_event_id, source_step_id=episode.step_id)
    original_action_shape = _extract_original_action_shape(
        source_events,
        source_event_id=episode.source_event_id,
        source_step_id=episode.step_id,
    )

    request, request_build_mode = _build_model_request(
        source_view=source_view,
        episode=episode,
        adapter=adapter,
        model_id=model_id,
    )
    response = adapter.invoke(request)
    zombie_action_shape = parse_action_shape_from_response(response)

    attempted_tool_calls_count = _attempted_tool_calls_count(response, zombie_action_shape)

    input_tokens = int(response.usage.get("input_tokens", max(1, len(request.request_bytes) // 4)))
    output_tokens = int(response.usage.get("output_tokens", 0))
    cost_usd_est = _estimate_cost_usd(
        pricing=pricing,
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    zombie_run_id = _new_zombie_run_id(batch_id=batch_id, episode_id=episode.episode_id)
    run_dir = batch_dir / zombie_run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    artifact_store = ArtifactStore(run_dir / "artifacts")
    request_ref, _ = artifact_store.write_json_canonical(_model_request_payload(request), content_type="application/json")
    response_ref, _ = artifact_store.write_json_canonical(_model_response_payload(response), content_type="application/json")

    parsed_action_payload = {
        "mode": MODE_REPLAY_DECISION,
        "episode_id": episode.episode_id,
        "source_run_id": episode.run_id,
        "source_step_id": episode.step_id,
        "original_action_shape": original_action_shape,
        "zombie_action_shape": zombie_action_shape,
        "phase_at_episode": phase_at_episode,
        "attempted_tool_calls_count": attempted_tool_calls_count,
    }
    parsed_action_ref, _ = artifact_store.write_json_canonical(parsed_action_payload, content_type="application/json")

    event_log = EventLog(run_dir / "event_log.jsonl", run_id=zombie_run_id)
    now = _utc_now()
    cwd = run_dir.as_posix()

    event_log.append_event(
        {
            "event_type": "run_START",
            "timestamp": now,
            "cwd": cwd,
            "mode": MODE_REPLAY_DECISION,
            "episode_id": episode.episode_id,
            "source_run_id": episode.run_id,
            "source_step_id": episode.step_id,
        }
    )
    event_log.append_event(
        {
            "event_type": "MODEL_CALL",
            "timestamp": now,
            "cwd": cwd,
            "mode": MODE_REPLAY_DECISION,
            "model_id": model_id,
            "request_build_mode": request_build_mode,
            "model_request_ref": request_ref.artifact_id,
            "model_request_hash": request.request_hash,
            "model_response_ref": response_ref.artifact_id,
            "model_response_hash": response.raw_hash,
            "finish_reason": response.finish_reason,
            "attempted_tool_calls_count": attempted_tool_calls_count,
            "artifact_refs": [request_ref.artifact_id, response_ref.artifact_id, parsed_action_ref.artifact_id],
        }
    )
    if attempted_tool_calls_count > 0:
        event_log.append_event(
            {
                "event_type": "TOOL_DENY",
                "timestamp": now,
                "cwd": cwd,
                "mode": MODE_REPLAY_DECISION,
                "deny_reason_code": "replay_decision_no_tools",
                "attempted_tool_calls_count": attempted_tool_calls_count,
                "artifact_refs": [parsed_action_ref.artifact_id],
            }
        )
    event_log.append_event(
        {
            "event_type": "METRIC_SUMMARY",
            "timestamp": now,
            "cwd": cwd,
            "mode": MODE_REPLAY_DECISION,
            "zombie_action_shape": zombie_action_shape,
            "original_action_shape": original_action_shape,
            "phase_at_episode": phase_at_episode,
            "coherent_for_phase": zombie_action_shape in VALID_ACTIONS_BY_PHASE[phase_at_episode],
            "artifact_refs": [parsed_action_ref.artifact_id],
        }
    )
    event_log.append_event(
        {
            "event_type": "run_END",
            "timestamp": now,
            "cwd": cwd,
            "mode": MODE_REPLAY_DECISION,
            "termination_reason": "zombie_complete",
        }
    )

    _write_event_log(path=run_dir / "event_log.jsonl", events=event_log.events)

    summary = {
        "mode": MODE_REPLAY_DECISION,
        "zombie_run_id": zombie_run_id,
        "episode_id": episode.episode_id,
        "source_run_id": episode.run_id,
        "source_step_id": episode.step_id,
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd_est": cost_usd_est,
        "attempted_tool_calls_count": attempted_tool_calls_count,
        "original_action_shape": original_action_shape,
        "zombie_action_shape": zombie_action_shape,
        "phase_at_episode": phase_at_episode,
        "coherent_for_phase": zombie_action_shape in VALID_ACTIONS_BY_PHASE[phase_at_episode],
        "request_artifact_ref": request_ref.artifact_id,
        "response_artifact_ref": response_ref.artifact_id,
        "parsed_action_artifact_ref": parsed_action_ref.artifact_id,
        "request_build_mode": request_build_mode,
    }

    (run_dir / "summary.json").write_text(canonical_json_dumps(summary) + "\n", encoding="utf-8")
    return ZombieEpisodeResult(zombie_run_id=zombie_run_id, run_dir=run_dir, summary=summary)


def _build_batch_summary(*, results: Sequence[ZombieEpisodeResult], batch_id: str, model_id: str) -> Dict[str, Any]:
    summaries = [item.summary for item in results]
    count = len(summaries)

    agreement_count = sum(1 for item in summaries if item["zombie_action_shape"] == item["original_action_shape"])
    coherence_count = sum(1 for item in summaries if bool(item["coherent_for_phase"]))
    distribution_counter: Counter[str] = Counter(item["zombie_action_shape"] for item in summaries)
    distribution = {shape: int(distribution_counter.get(shape, 0)) for shape in ACTION_SHAPES}

    dominant_count = max(distribution.values()) if distribution else 0
    over_reliance = (dominant_count / count) > 0.8 if count > 0 else False

    total_input_tokens = sum(int(item["input_tokens"]) for item in summaries)
    total_output_tokens = sum(int(item["output_tokens"]) for item in summaries)
    total_cost_usd_est = round(sum(float(item["cost_usd_est"]) for item in summaries), 10)

    return {
        "schema_version": "frugal_zombie_batch.v1",
        "mode": MODE_REPLAY_DECISION,
        "batch_id": batch_id,
        "model_id": model_id,
        "episode_count": count,
        "agreement_rate": round(agreement_count / count, 6) if count else 0.0,
        "behavioral_distribution": distribution,
        "behavioral_distribution_over_reliance": over_reliance,
        "coherence_rate": round(coherence_count / count, 6) if count else 0.0,
        "cumulative_cost_line": {
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd_est": total_cost_usd_est,
            "model_id": model_id,
        },
        "episode_runs": [
            {
                "zombie_run_id": item.zombie_run_id,
                "run_dir": item.run_dir.as_posix(),
                "summary_path": (item.run_dir / "summary.json").as_posix(),
            }
            for item in results
        ],
    }


def _verify_batch_outputs(*, results: Sequence[ZombieEpisodeResult], batch_summary: Mapping[str, Any]) -> None:
    required_metrics = {"agreement_rate", "behavioral_distribution", "coherence_rate"}
    missing = sorted(metric for metric in required_metrics if metric not in batch_summary)
    if missing:
        raise ZombieRunError(f"Batch summary missing required metrics: {', '.join(missing)}")

    for result in results:
        summary = result.summary
        if summary.get("cost_usd_est") is None:
            raise ZombieRunError(f"Missing non-null cost_usd_est in {result.run_dir / 'summary.json'}")

    for result in results:
        events = _load_source_events(result.run_dir / "event_log.jsonl")
        for event in events:
            if event.event_type == "TOOL_CALL":
                raise ZombieRunError(f"TOOL_CALL event found in zombie output: {result.run_dir}")


def _build_model_request(
    *,
    source_view,
    episode: EpisodeRecord,
    adapter: ModelAdapter,
    model_id: str,
) -> Tuple[ModelRequest, str]:
    try:
        context_pack_payload = source_view.artifact_store.load_json(episode.context_pack_ref)
        projection = ContextPackProjection(context_pack_payload)
        request = adapter.format_context(projection)
        return _with_model_id(request, model_id), "projection"
    except Exception:
        pass

    try:
        recorded = source_view.artifact_store.load_json(episode.model_request_ref)
    except Exception as exc:
        raise ZombieRunError(
            f"Failed to build model request for episode {episode.episode_id}: projection and fallback both failed"
        ) from exc

    return (
        ModelRequest(
            system_prompt=str(recorded.get("system_prompt", "")),
            messages=list(recorded.get("messages", [])) if isinstance(recorded.get("messages"), list) else [],
            tools=list(recorded.get("tools", [])) if isinstance(recorded.get("tools"), list) else [],
            model_identifier=model_id,
            max_tokens=int(recorded.get("max_tokens", 4096)),
            temperature=float(recorded.get("temperature", 0.0)),
        ),
        "recorded_request_fallback",
    )


def _extract_original_action_shape(
    events: Sequence[Event],
    *,
    source_event_id: str,
    source_step_id: int,
) -> str:
    start_idx = _find_source_event_index(events, source_event_id=source_event_id, source_step_id=source_step_id)

    for idx in range(start_idx + 1, len(events)):
        event = events[idx]
        raw_event_type = str(event.payload.get("event_type", "")).lower()
        if idx > start_idx + 1 and event.event_type == "CONTEXT_SLICE_BOUND":
            break
        if idx > start_idx + 1 and raw_event_type in {"context_slice_bound", "contextslice_binding"}:
            break

        mapped = _map_event_to_action_shape(event)
        if mapped is not None:
            return mapped

    return ACT_REFUSE


def _phase_at_episode(events: Sequence[Event], *, source_event_id: str, source_step_id: int) -> str:
    idx = _find_source_event_index(events, source_event_id=source_event_id, source_step_id=source_step_id)
    phase = "Orient"
    for event in events[: idx + 1]:
        if event.event_type != "PHASE_TRANSITION":
            continue
        to_phase = event.payload.get("to_phase")
        normalized = _normalize_phase(to_phase)
        if normalized is not None:
            phase = normalized
    return phase


def _find_source_event_index(events: Sequence[Event], *, source_event_id: str, source_step_id: int) -> int:
    for idx, event in enumerate(events):
        if event.event_id == source_event_id:
            return idx

    for idx, event in enumerate(events):
        if event.step_id == source_step_id and event.event_type == "CONTEXT_SLICE_BOUND":
            return idx
        raw = str(event.payload.get("event_type", "")).lower()
        if event.step_id == source_step_id and raw in {"context_slice_bound", "contextslice_binding"}:
            return idx

    raise ZombieRunError(f"Unable to locate source context slice event (event_id={source_event_id}, step_id={source_step_id})")


def _map_event_to_action_shape(event: Event) -> Optional[str]:
    if event.event_type == "TOOL_CALL":
        return ACT_TOOL
    if event.event_type in {"VERIFIER_run", "VERIFIER_RESULT"}:
        return ACT_VERIFY
    if event.event_type in {"PLAN_UPDATE", "PLAN_STATUS_CHANGED", "PLAN_STEP_STATUS", "PLAN_DEFINED"}:
        return ACT_PLAN_UPDATE
    if event.event_type in {"REANCHOR_START", "REANCHOR_END", "REANCHOR_REPEAT_DETECTED"}:
        return ACT_REANCHOR

    raw_event_type = str(event.payload.get("event_type", "")).lower()
    if event.event_type == "MODEL_CALL" or raw_event_type in {"model_response", "model_call"}:
        finish_reason = str(event.payload.get("finish_reason", "")).lower()
        if "tool" in finish_reason:
            return ACT_TOOL
        text = _coalesce_text(event.payload)
        if text:
            inferred = _infer_text_action_shape(text)
            if inferred is not None:
                return inferred

    return None


def _infer_text_action_shape(text: str) -> Optional[str]:
    lowered = text.lower()
    if _contains_any(lowered, ("reanchor", "re-anchor", "reset assumptions", "revisit hypothesis")):
        return ACT_REANCHOR
    if _contains_any(lowered, ("verify", "verification", "run tests", "unit test", "validate", "assert")):
        return ACT_VERIFY
    if _contains_any(lowered, ("plan update", "update plan", "next steps", "roadmap", "plan")):
        return ACT_PLAN_UPDATE
    if _contains_any(lowered, ("cannot", "can't", "unable", "refuse", "won't")):
        return ACT_REFUSE
    return None


def _coalesce_text(payload: Mapping[str, Any]) -> str:
    for key in ("text_content", "response_text", "assistant_text", "content", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _attempted_tool_calls_count(response: ModelResponse, action_shape: str) -> int:
    if response.tool_calls:
        return len(response.tool_calls)
    finish_reason = (response.finish_reason or "").lower()
    if action_shape == ACT_TOOL or "tool" in finish_reason:
        return 1
    return 0


def _load_or_init_pricing(path: Path) -> Mapping[str, Any]:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ZombieRunError(f"Invalid model pricing file: {path}")
        return data

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json_dumps(DEFAULT_PRICING_CONFIG) + "\n", encoding="utf-8")
    return DEFAULT_PRICING_CONFIG


def _estimate_cost_usd(*, pricing: Mapping[str, Any], model_id: str, input_tokens: int, output_tokens: int) -> float:
    models = pricing.get("models") if isinstance(pricing.get("models"), dict) else {}
    model_prices = models.get(model_id)
    if not isinstance(model_prices, dict):
        raise ZombieRunError(f"Missing pricing for model_id={model_id}")

    input_rate = float(model_prices.get("input_per_1m_tokens_usd", 0.0))
    output_rate = float(model_prices.get("output_per_1m_tokens_usd", 0.0))

    cost = (max(0, int(input_tokens)) / 1_000_000.0) * input_rate
    cost += (max(0, int(output_tokens)) / 1_000_000.0) * output_rate
    return round(cost, 10)


def _build_adapter(*, adapter_mode: str, model_id: str) -> ModelAdapter:
    if adapter_mode != "mock":
        raise ZombieRunError(f"Unsupported adapter_mode={adapter_mode!r}; use 'mock'")
    return LocalMockZombieAdapter(model_id=model_id)


def _load_episodes(path: str | Path) -> List[EpisodeRecord]:
    episodes: List[EpisodeRecord] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise ZombieRunError("Episode line must be a JSON object")
        episode_type = str(payload.get("episode_type", "context_slice"))
        if episode_type != "context_slice":
            continue
        episodes.append(EpisodeRecord.from_dict(payload))
    return episodes


def _load_source_events(path: Path) -> List[Event]:
    events: List[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        raw = json.loads(stripped)
        if not isinstance(raw, dict):
            continue

        event_type = raw.get("event_type")
        try:
            canonical = canonicalize_event_type(event_type)
        except ValueError:
            if isinstance(event_type, str) and event_type.strip():
                canonical = event_type.strip().upper()
            else:
                canonical = "UNKNOWN_EVENT_TYPE"

        payload = dict(raw)
        payload["event_type"] = canonical
        events.append(
            Event(
                event_id=str(raw.get("event_id", "")),
                prev_event_hash=str(raw.get("prev_event_hash", "")),
                event_type=canonical,
                step_id=int(raw.get("step_id", -1)) if isinstance(raw.get("step_id"), int) else -1,
                timestamp=str(raw.get("timestamp", "")),
                cwd=str(raw.get("cwd", "")),
                payload=payload,
            )
        )
    return events


def _with_model_id(request: ModelRequest, model_id: str) -> ModelRequest:
    return ModelRequest(
        system_prompt=request.system_prompt,
        messages=request.messages,
        tools=request.tools,
        model_identifier=model_id,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )


def _model_request_payload(request: ModelRequest) -> Dict[str, Any]:
    return {
        "system_prompt": request.system_prompt,
        "messages": request.messages,
        "tools": request.tools,
        "model_identifier": request.model_identifier,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "request_hash": request.request_hash,
    }


def _model_response_payload(response: ModelResponse) -> Dict[str, Any]:
    return {
        "raw_hash": response.raw_hash,
        "finish_reason": response.finish_reason,
        "text_content": response.text_content,
        "tool_calls": [
            {
                "tool_name": call.tool_name,
                "tool_args": call.tool_args,
                "call_id": call.call_id,
                "index": call.index,
            }
            for call in response.tool_calls
        ],
        "usage": response.usage,
        "candidate_count": response.candidate_count,
        "normalization_warnings": response.normalization_warnings,
    }


def _write_event_log(*, path: Path, events: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("\n".join(canonical_json_dumps(dict(event)) for event in events) + "\n", encoding="utf-8")


def _normalize_phase(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    for phase in PHASES:
        if normalized == phase.lower():
            return phase
    return None


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _required_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    raise ZombieRunError(f"Episode missing required field {key}")


def _required_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, int):
        return value
    raise ZombieRunError(f"Episode missing required int field {key}")


def _new_batch_id(*, model_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    model_part = model_id.replace("/", "-").replace(" ", "-")
    return f"zombie_batch_{model_part}_{stamp}"


def _new_zombie_run_id(*, batch_id: str, episode_id: str) -> str:
    return f"{batch_id}_{episode_id[:12]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run REPLAY_DECISION Zombie evaluation on episodes")
    parser.add_argument("--episodes", required=True, help="Path to episodes.jsonl")
    parser.add_argument(
        "--out-root",
        default="runs/frugal/zombie",
        help="Directory where zombie batch outputs are created",
    )
    parser.add_argument("--model-id", default="mock-zombie-v1", help="Model identifier used for logging/costing")
    parser.add_argument("--adapter", default="mock", help="Adapter mode (currently only: mock)")
    parser.add_argument("--limit", type=int, default=10, help="Max episodes to evaluate in this batch")
    parser.add_argument("--offset", type=int, default=0, help="Episode offset")
    parser.add_argument(
        "--pricing-file",
        default=str(Path(__file__).with_name("model_pricing.json")),
        help="Path to model_pricing.json",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = run_zombie_batch(
            episodes_path=args.episodes,
            out_root=args.out_root,
            model_id=args.model_id,
            adapter_mode=args.adapter,
            limit=args.limit,
            offset=args.offset,
            pricing_path=args.pricing_file,
        )
    except ZombieRunError as exc:
        print(f"error: {exc}")
        return 2

    print(
        "batch_id={batch_id} episode_count={episode_count} batch_dir={batch_dir} batch_summary={batch_summary_path}".format(
            **result
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
