"""Opt-in arm: a turn that cannot be parsed never ends the run while budget remains.

Control ends the run with ``solver_protocol_failure`` once the in-step schema corrections
(two) are spent. Under ``resilient_v1`` that unparseable turn is instead recorded as an
ordinary failed observation: one turn is consumed, the factual observation below is carried
in the next request, and the loop continues. Termination happens only after
``MAX_CONSECUTIVE_UNPARSEABLE_TURNS`` consecutive unparseable turns, or when the existing
turn/step/time budgets run out. Nothing is guessed or repaired on the model's behalf.

``resilient_v2`` is ``resilient_v1`` plus output-cap handling: no escalation retry, and a solver turn
that ends at the output cap with no action becomes an observation carrying the tail of its own
reasoning (``output_cap_observation``) instead of ending the run. It shares the consecutive-failure
termination with unparseable turns.

``resilient_v3`` is ``resilient_v2`` plus a reasoning-effort step-down: after an output-cap turn with
no action the next solver request uses one effort level lower (``max``>``high``>``medium``>``low``,
floor ``low``), stepping down again on each further consecutive cap turn; any other turn restores the
configured level. The observation states the effort in force as a fact.

``resilient_v4`` is ``resilient_v2`` plus a retry temperature: every solver request issued as a corrective
retry after a protocol/parse rejection (the in-step schema corrections, and the turn that carries the
failure observation) is sampled at ``max(base, RETRY_TEMPERATURE)``; the next ordinary turn returns to the
base temperature. Greedy decoding otherwise reproduces the identical malformed call on every retry.
"""
from __future__ import annotations

import argparse
from typing import Any, Mapping

from .persistent_flat_advanced import FLAT_SHAPE_EXAMPLES

CONTROL = "control"
RESILIENT_V1 = "resilient_v1"
RESILIENT_V2 = "resilient_v2"
RESILIENT_V3 = "resilient_v3"
RESILIENT_V4 = "resilient_v4"
RESILIENT_V5 = "resilient_v5"
SUPPORTED_PROTOCOL_RESILIENCE = frozenset({CONTROL, RESILIENT_V1, RESILIENT_V2, RESILIENT_V3, RESILIENT_V4, RESILIENT_V5})
RESILIENT_MODES = frozenset({RESILIENT_V1, RESILIENT_V2, RESILIENT_V3, RESILIENT_V4, RESILIENT_V5})
OUTPUT_CAP_MODES = frozenset({RESILIENT_V2, RESILIENT_V3, RESILIENT_V4})
RETRY_TEMPERATURE_MODES = frozenset({RESILIENT_V4})
TOLERANT_ARGUMENT_MODES = frozenset({RESILIENT_V5})
RETRY_TEMPERATURE = 0.7
EFFORT_LADDER = ("low", "medium", "high", "max")
EFFORT_STEPDOWN_COUNTER = "effort_stepdowns"
EFFORT_TURN_COUNTER = "solver_effort_turns"
PROTOCOL_RESILIENCE_ENV = "AETHER_G4_PROTOCOL_RESILIENCE"
MAX_CONSECUTIVE_UNPARSEABLE_TURNS = 6
RAW_ARGUMENTS_LIMIT = 2000
FAILED_TURNS_COUNTER = "protocol_failed_turns"
RECOVERED_COUNTER = "protocol_recovered"
OUTPUT_CAP_COUNTER = "output_cap_turns"
OUTPUT_CAP_REASONING_TAIL_CHARS = 4000


class ProtocolResilienceError(ValueError):
    """An unknown protocol-resilience mode was supplied."""


def resolve_protocol_resilience(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(PROTOCOL_RESILIENCE_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_PROTOCOL_RESILIENCE:
        raise ProtocolResilienceError(f"unknown protocol resilience mode: {selected!r}")
    return selected


def add_protocol_resilience_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--protocol-resilience", choices=sorted(SUPPORTED_PROTOCOL_RESILIENCE), default=CONTROL,
        help="continue past an unparseable turn as a failed observation instead of ending the run (opt-in)",
    )


def build_protocol_resilience_launch_binding(mode: str | None) -> dict[str, Any]:
    selected = resolve_protocol_resilience(mode)
    manifest: dict[str, Any] = {"protocol_resilience": selected}
    if selected in RETRY_TEMPERATURE_MODES:
        manifest["protocol_resilience_retry_temperature"] = RETRY_TEMPERATURE
    return {
        "protocol_resilience": selected,
        "env": {PROTOCOL_RESILIENCE_ENV: selected},
        "manifest": manifest,
    }


def retry_temperature(base: float) -> float:
    """Temperature for a corrective retry: never below the base temperature."""
    return max(float(base), RETRY_TEMPERATURE)


def failure_observation(error: BaseException) -> str:
    """Model-visible, factual account of one turn that could not be parsed."""
    tool = str(getattr(error, "rejected_tool_name", "") or "").strip() or "unknown (no tool call recovered)"
    raw = str(getattr(error, "rejected_tool_arguments", "") or "")
    example = FLAT_SHAPE_EXAMPLES.get(tool)
    shape = (
        f"Required argument shape: one flat JSON object, for example {example}."
        if example is not None else
        'Required argument shape: the tool arguments as one JSON object (not a JSON-encoded string), '
        'for example {"arguments": {...}}.'
    )
    parts = [
        "[solver_protocol_observation] Your previous turn could not be parsed and was not executed, "
        "so no task action occurred.",
        f"Tool: {tool}.",
        f"Parse error: {error}",
    ]
    if raw:
        clipped = raw[:RAW_ARGUMENTS_LIMIT]
        parts.append(f"Rejected raw arguments{' (clipped)' if len(raw) > len(clipped) else ''}: {clipped}")
    parts.append(shape)
    parts.append("Reply with exactly one valid tool call.")
    return " ".join(parts)


def stepped_effort(configured: str, consecutive_cap_turns: int) -> str:
    """Effort for the next request: ``configured`` lowered one level per consecutive cap turn, floor ``low``."""
    if configured not in EFFORT_LADDER:
        raise ProtocolResilienceError(f"reasoning effort {configured!r} is not on the step-down ladder {EFFORT_LADDER}")
    index = EFFORT_LADDER.index(configured) - max(0, int(consecutive_cap_turns))
    return EFFORT_LADDER[max(0, index)]


def effort_line(effort: str) -> str:
    return f"Reasoning effort for this turn: {effort} (reduced after the output-limit turn)."


def output_cap_observation(output_tokens: int | None, reasoning: str | None, effort: str | None = None) -> str:
    """Model-visible account of one turn that hit the output cap without acting."""
    head = (
        f"[solver_output_cap_observation] Your previous turn reached the {output_tokens if output_tokens else 'configured'}-token "
        "output limit while reasoning and produced no action, so nothing ran. The final part of that "
        "reasoning follows so you can continue from it; take an action this turn."
    )
    if effort is not None:
        head = f"{head}\n{effort_line(effort)}"
    tail = str(reasoning or "")[-OUTPUT_CAP_REASONING_TAIL_CHARS:]
    if not tail:
        return head
    return f"{head}\n\nYour own prior reasoning (last {len(tail)} characters):\n{tail}"


def output_cap_observation_for(error: BaseException | None, effort: str | None = None) -> str:
    """Build the observation from the cap-truncation evidence found on ``error`` or its causes."""
    seen: set[int] = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if getattr(error, "code", "") == "provider_output_truncated":
            return output_cap_observation(getattr(error, "output_tokens", None), getattr(error, "reasoning_content", ""), effort)
        error = error.__cause__
    return output_cap_observation(None, "", effort)
