"""Launcher environment -> CoreConfig: every AETHER_CORE_* setting, its allowed values, and the refusals for
missing, invalid or removed settings (split from harbor_agent.py, module cap)."""

from __future__ import annotations

import os
from typing import Any, Mapping

from . import fork
from .clm import CHECKPOINT_POLICIES, NOTES_VOICES, REPLAY_MODES, ClmSettings
from .clm_settings import CLM_PROFILES, META_PROFILE
from .loop import CONTEXT_MODES, CoreConfig
from .oversight import ReviewPlan
from .diffcheck import DIFFCHECK_ENV, DIFFCHECK_MODES
from .open_issues import OPEN_ISSUES_ENV
from .rival import RIVAL_ENV, RIVAL_MODES
from .start_copy import START_COPY_ENV
from .mcp import MCP_IDEMPOTENCY_ENV
from .outside_witness import OUTSIDE_WITNESS_ENV
from . import state_service
from .image_region import IMAGE_COMPARE_ENV, IMAGE_REGION_ENV
from .record import HOLD_ENV, HOLD_MODES, RECORD_ENV, RECORD_MODES
from .tools import HYGIENE_MODES


REVIEW_ENV = "AETHER_CORE_REVIEW"
REVIEW_MODES = ("off", "jev", "jev_progress")
CONTEXT_ENV = "AETHER_CORE_CONTEXT"
REPL_ENV = "AETHER_CORE_REPL"
REPL_MODES = ("on", "off"); FACTS_MODES = ("off", "on", "pull", "v2")
IMAGES_ENV = "AETHER_CORE_IMAGES"
CHECKPOINT_POLICY_ENV = "AETHER_CORE_CHECKPOINT_POLICY"
PARALLEL_ENV = "AETHER_CORE_PARALLEL_READS"
# Optional; "many" is an experimental provider setting. Earlier R2/N1/N2 arm e failed; the default remains "one".
CALLS_ENV, CALLS_MODES = "AETHER_CORE_CALLS", ("one", "many")
# optional; unset means "newest" (only the latest turn's reasoning is sent back); "all" sends every turn's back.
REASONING_ENV = "AETHER_CORE_REASONING"
NATIVE_COMPACTION_ENV = "AETHER_CORE_NATIVE_COMPACTION"  # optional token threshold (Responses only; E18 K1)
CHAIN_ENV = "AETHER_CORE_CHAIN"  # optional on/off (Responses only): previous_response_id chaining, stored responses
IMAGE_BATCH_ENV = "AETHER_CORE_IMAGE_BATCH"  # images leave the request in groups (images.limit); 4 = default (board IB)
TOOL_STRICT_ENV = "AETHER_CORE_TOOL_STRICT"  # study arm SF: "off" sends strict=false on Responses tools
MAX_OUTPUT_ENV = "AETHER_CORE_MAX_OUTPUT"  # optional; per-turn output ceiling in tokens (default 16384); see _max_output
BUDGET_ENV = "AETHER_CORE_CONTEXT_BUDGET"  # optional; editable-context tokens (default 32000); see _budget
# optional; unset means "off". "once": one independent check of the first finish by the same model in a fresh
# context on a clone (see verify). SELF_CHECK=on adds the self-check paragraph (tools.SELF_CHECK_DOC).
VERIFY_ENV, VERIFY_MODES = "AETHER_CORE_VERIFY", ("off", "once")
SELF_CHECK_ENV, STATE_ENV = "AETHER_CORE_SELF_CHECK", "AETHER_CORE_STATE"  # STATE=on: run state (see runstate)
END_PROCESSES_ENV = "AETHER_CORE_END_PROCESSES"  # optional; unset means "keep" (the default); see loop.CoreConfig
END_PROCESSES_MODES = ("stop", "keep")
HYGIENE_ENV = "AETHER_CORE_HYGIENE"  # optional; unset means "off"; on/placebo: tools.HYGIENE_DOC
NOTES_ENV = "AETHER_CORE_NOTES"  # own: edited context and checkpoints labelled as the model's notes (still role=user); legacy (default)
CONTEXT_EVIDENCE_ENV = "AETHER_CORE_CONTEXT_EVIDENCE_PRESENTATION"
INTENT_ENV = "AETHER_CORE_INTENT"  # on: every action tool takes the model's reason and expected result (see intent)
FORK_ENV = "AETHER_CORE_FORK"  # on: experiment instrument, matched continuations at the first finish (fork)
# optional; unset means "chat" (the GLM request). "reasoning": max_completion_tokens, no sampling parameters.
REQUEST_ENV = "AETHER_CORE_REQUEST"
WIRE_ENV = "AETHER_CORE_REASONING_WIRE"  # optional; where the provider carries reasoning (see reasoning_wire)
REQUEST_SHAPES = ("chat", "reasoning", "responses")  # responses: /v1/responses, native tools + reasoning replay
PROGRESS_AT = (0.35, 0.70)
ENDPOINT_ENV, API_ENV = "AETHER_FW_GLM_53_FLASH_ENDPOINT", "AETHER_CORE_API"  # API: azure (default) or openai
KEY_ENV = "AETHER_FW_GLM_53_FLASH_KEY"
DEPLOYMENT_ENV = "AETHER_FW_GLM_53_FLASH_DEPLOYMENT"
EFFORT_ENV, DEADLINE_ENV = "AETHER_TB4_REASONING_EFFORT", "AETHER_AGENT_DEADLINE_SEC"
SAMPLING = {"temperature": 1.0, "top_p": 0.95}  # identical to the s10c solver for a fair comparison
JEV_MAX_CALLS, JEV_CAP_GBP = 6, "0.10"
CALLS_FILE = "core_calls.jsonl"  # every provider request and response (see calls)
JEV_TIMEOUT_S = 30.0


class ConfigError(RuntimeError):
    """The launcher did not provide a valid Aether Core configuration."""


# Removed flags (experiments failed). Only the value that equals the surviving baseline is accepted; any other
# non-empty value asks for behaviour that no longer exists and stops the run.
REMOVED_ENV = {
    "AETHER_CORE_TURN": "tool", "AETHER_CORE_FINISH": "direct", "AETHER_CORE_FINISH_CHECK": None,
    "AETHER_CORE_EVIDENCE": "off", "AETHER_CORE_LEDGER": "off", "AETHER_CORE_READBACK": "off",
    "AETHER_CORE_THINK": "off", "AETHER_CORE_PROBE": "off", "AETHER_CORE_VIEW": "off",
    "AETHER_CORE_RESERVE": "off", "AETHER_CORE_TEMPERATURE": None,
}


def _refuse_removed(environ: Mapping[str, str]) -> None:
    for name, baseline in REMOVED_ENV.items():
        value = environ.get(name, "").strip()
        if value and value != baseline:
            raise ConfigError(f"{name}={value!r}: this setting was removed (its experiment failed); unset it")


def _required(name: str, environ: Mapping[str, str]) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def build_config(*, environ: Mapping[str, str] | None = None) -> CoreConfig:
    from .evidence_context import CONTEXT_EVIDENCE_MODES
    environ = os.environ if environ is None else environ
    _refuse_removed(environ)
    review = environ.get(REVIEW_ENV, "").strip()
    context = environ.get(CONTEXT_ENV, "").strip()
    repl = environ.get(REPL_ENV, "").strip()
    if review not in REVIEW_MODES:
        raise ConfigError(f"{REVIEW_ENV} must be one of {REVIEW_MODES}, got {review!r}")
    if context not in CONTEXT_MODES:
        raise ConfigError(
            f"{CONTEXT_ENV} must be one of {CONTEXT_MODES}, got {context!r}"
        )
    if repl not in REPL_MODES:
        raise ConfigError(f"{REPL_ENV} must be one of {REPL_MODES}, got {repl!r}")
    see = environ.get(IMAGES_ENV, "").strip()
    if see not in REPL_MODES:
        raise ConfigError(f"{IMAGES_ENV} must be one of {REPL_MODES}, got {see!r}")
    plan = (
        ReviewPlan(finish=False)
        if review == "off"
        else ReviewPlan()
        if review == "jev"
        else ReviewPlan(progress_at=PROGRESS_AT, final=True)
    )
    return CoreConfig(
        context=context,
        repl=repl == "on",
        images=see == "on",
        reviews=plan,
        clm=ClmSettings(
            replay_reasoning=_replay(environ, context),
            **_budget(environ),
            **_clm_profile(environ),
            reminder_room_tokens=2_048 if _choice(environ, "AETHER_CORE_CLM_NUDGES", ("core", "late"), "core") == "late"
            else 0,
            notes_voice=_choice(environ, NOTES_ENV, NOTES_VOICES, "legacy"),
            attest_original_history=(
                _choice(environ, CONTEXT_EVIDENCE_ENV, CONTEXT_EVIDENCE_MODES, "off") != "off"
            ),
            image_batch=int(_choice(environ, IMAGE_BATCH_ENV, ("1", "2", "3", "4", "6", "8"), "4")),
        ),
        parallel_reads=_parallel_reads(environ),
        terminal_events=_choice(environ, "AETHER_CORE_TERMINAL_EVENTS", REPL_MODES, "off") == "on",
        fast_process_scan=_choice(environ, "AETHER_CORE_FAST_PROCESS_SCAN", REPL_MODES, "off") == "on",
        fast_mcp_wait=_choice(environ, "AETHER_CORE_FAST_MCP_WAIT", REPL_MODES, "off") == "on",
        keep_cut_outputs=_choice(environ, "AETHER_CORE_KEEP_CUT_OUTPUTS", REPL_MODES, "off") == "on",
        append_policy=environ.get("AETHER_CORE_APPEND_POLICY", "").strip() or "core64",
        context_window=_window(environ),
        finish_settle=_choice(environ, "AETHER_CORE_FINISH_SETTLE", REPL_MODES, "off") == "on",
        finish_facts=_choice(environ, "AETHER_CORE_FINISH_FACTS", REPL_MODES, "off") == "on",
        env_map=_choice(environ, "AETHER_CORE_ENV_MAP", REPL_MODES, "off") == "on",
        rehydrate=_choice(environ, "AETHER_CORE_REHYDRATE", REPL_MODES, "off") == "on",
        workspace_search=_choice(environ, "AETHER_CORE_WORKSPACE_SEARCH", REPL_MODES, "off") == "on",
        check_versions=_choice(environ, "AETHER_CORE_CHECK_VERSIONS", REPL_MODES, "off") == "on",
        session_log=_choice(environ, "AETHER_CORE_SESSION_LOG", REPL_MODES, "off") == "on",
        completion_notices=_choice(environ, "AETHER_CORE_COMPLETION_NOTICES", REPL_MODES, "off") == "on",
        auto_wait=_choice(environ, "AETHER_CORE_AUTO_WAIT", REPL_MODES, "off") == "on",
        auto_wait_grace_s=float(_choice(environ, "AETHER_CORE_AUTO_WAIT_GRACE", ("30", "1"), "30")),
        # Default on since 16 Nov (lean screen F + H2 holdout): facts appended, never rewritten in place; the
        # rewrites put 10-12% of input on the uncached rate. Cost 0.52x (screen) and 0.62x (holdout), passes equal.
        stable_facts=_choice(environ, "AETHER_CORE_STABLE_FACTS", REPL_MODES, "on") == "on",
        terminal_result_delivery=_choice(environ, "AETHER_CORE_TERMINAL_RESULT_DELIVERY", REPL_MODES, "off") == "on",
        workspace_brief=_choice(environ, "AETHER_CORE_WORKSPACE_BRIEF", REPL_MODES, "off") == "on",
        verify=_choice(environ, VERIFY_ENV, VERIFY_MODES, "off") == "once",
        self_check=_choice(environ, SELF_CHECK_ENV, REPL_MODES, "off") == "on",
        intent=_choice(environ, INTENT_ENV, REPL_MODES, "off") == "on",
        **_fork(environ),
        end_processes=_choice(environ, END_PROCESSES_ENV, END_PROCESSES_MODES, "keep"),
        hygiene=_choice(environ, HYGIENE_ENV, HYGIENE_MODES, "off"), state=_choice(environ, STATE_ENV, REPL_MODES, "off") == "on",
        **_record(environ),
        diffcheck=_choice(environ, DIFFCHECK_ENV, DIFFCHECK_MODES, "off") == "on",
        evidence_presentation=_choice(
            environ, CONTEXT_EVIDENCE_ENV, CONTEXT_EVIDENCE_MODES, "off"
        ),
        **_max_output(environ),
        open_issues=_choice(environ, OPEN_ISSUES_ENV, REPL_MODES, "off") == "on",
        rival=_choice(environ, RIVAL_ENV, RIVAL_MODES, "off") == "on",
        exec_check=_choice(environ, RIVAL_ENV, RIVAL_MODES, "off") == "exec",
        card=_choice(environ, RIVAL_ENV, RIVAL_MODES, "off") in ("card", "probe", "challenge", "attack", "observe", "forks"),
        card_probe=_choice(environ, RIVAL_ENV, RIVAL_MODES, "off") == "probe",
        card_challenge={"challenge": "challenge", "attack": "attack", "observe": "observe", "forks": "forks"}.get(_choice(environ, RIVAL_ENV, RIVAL_MODES, "off"), ""),
        start_copy=_choice(environ, START_COPY_ENV, REPL_MODES, "on") == "on",  # default on since y8/y9 (LOG 28 Oct)
        outside_witness=_choice(environ, OUTSIDE_WITNESS_ENV, REPL_MODES, "off") == "on",  # A21
        mcp_idempotency=_choice(environ, MCP_IDEMPOTENCY_ENV, REPL_MODES, "off") == "on",  # A14
        browser_page_facts=_choice(environ, "AETHER_CORE_BROWSER_PAGE_FACTS", REPL_MODES, "off") == "on",  # C3
        browser_effects=_choice(environ, "AETHER_CORE_BROWSER_EFFECTS", REPL_MODES, "off") == "on",  # C16
        task_at_first_observation=environ.get("AETHER_CORE_TASK_AT_FIRST_OBS") == "on", stated_use=environ.get("AETHER_CORE_STATED_USE") == "on", working=environ.get("AETHER_CORE_WORKING", "on"), start_note=environ.get("AETHER_CORE_START_NOTE", "start"), task_appendix_file=environ.get("AETHER_CORE_TASK_APPENDIX_FILE", ""), step0_file=environ.get("AETHER_CORE_STEP0_FILE", ""), agenda=environ.get("AETHER_CORE_AGENDA", "off"),  # study arms
        **state_service.settings(lambda name, modes, unset: _choice(environ, name, modes, unset), REPL_MODES, FACTS_MODES),
        image_region=_choice(environ, IMAGE_REGION_ENV, REPL_MODES, "off") == "on",
        image_compare=_choice(environ, IMAGE_COMPARE_ENV, REPL_MODES, "off") == "on",
        toolset=_choice(environ, "AETHER_CORE_TOOLSET", ("full", "minimal", "python", "codex"), "full"),  # T0; B18; CX
        task_repeat=int(_choice(environ, "AETHER_CORE_TASK_REPEAT", ("1", "2", "3"), "1")),  # study arm R2
        image_effort=_choice(environ, "AETHER_CORE_IMAGE_EFFORT", ("", "low", "medium", "high", "xhigh"), ""))


def _max_output(environ: Mapping[str, str]) -> dict:
    """The per-turn output ceiling. The rate limiter admits each request by prompt plus this ceiling, so an unused
    ceiling spends rate-limit headroom (mission 2026-10-28: 31% of run time in rate-limit waits; 1 of 2910 turns
    over 16k output tokens)."""
    raw = environ.get(MAX_OUTPUT_ENV, "").strip()
    if not raw:
        return {}
    if not raw.isdigit() or int(raw) < 4_096:
        raise ConfigError(f"{MAX_OUTPUT_ENV} must be an integer number of tokens >= 4096")
    return {"max_output_tokens": int(raw)}


def _record(environ: Mapping[str, str]) -> dict:
    mode, hold = _choice(environ, RECORD_ENV, RECORD_MODES, "off"), _choice(environ, HOLD_ENV, HOLD_MODES, "off")
    if mode != "off" and hold != "off":
        raise ConfigError(f"{RECORD_ENV} and {HOLD_ENV} both act at the first finish; use one")
    return {"record": mode != "off", "record_measure": mode in ("measure", "paths", "coverage"), "finish_hold": hold,
            "record_paths": mode in ("paths", "coverage"), "record_commands": mode == "coverage"}


def _native_compaction(environ: Mapping[str, str]) -> int | None:
    """Off unless set to a token threshold; anything else stops the run (no silent default)."""
    raw = environ.get(NATIVE_COMPACTION_ENV, "").strip()
    if raw in ("", "off"):
        return None
    if not raw.isdigit():
        raise ValueError(f"{NATIVE_COMPACTION_ENV} must be off or a token threshold, got {raw!r}")
    return int(raw)


def _choice(
    environ: Mapping[str, str], name: str, modes: tuple[str, ...], unset: str
) -> str:
    """An optional setting: unset means ``unset`` (the baseline); anything outside ``modes`` stops the run."""
    value = environ.get(name, unset).strip() or unset
    if value not in modes:
        raise ConfigError(f"{name} must be one of {', '.join(modes)}, got {value!r}")
    return value


def _fork(environ: Mapping[str, str]) -> dict[str, Any]:
    on = _choice(environ, FORK_ENV, REPL_MODES, "off") == "on"
    if on and _choice(environ, VERIFY_ENV, VERIFY_MODES, "off") != "off":
        raise ConfigError(f"{FORK_ENV} and {VERIFY_ENV} both act at the first finish; use one")
    try:
        keep = on and _choice(environ, fork.KEEP_ENV, REPL_MODES, "off") == "on"
        return {"fork": on, "fork_arms": fork.load_arms(environ) if on else (), "fork_keep": keep}
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def _request_shape(environ: Mapping[str, str]) -> str:
    return _choice(environ, REQUEST_ENV, REQUEST_SHAPES, "chat")


def _replay(environ: Mapping[str, str], context: str) -> str:
    value = environ.get(REASONING_ENV, "newest").strip() or "newest"
    if value not in REPLAY_MODES:
        raise ConfigError(f"{REASONING_ENV} must be one of {', '.join(REPLAY_MODES)}")
    # "all" on chat (overnight E7): chat assistant messages carry reasoning_content like the newest turn already
    # does. Under "all", CLM's held() leaves every replayed reasoning out of the budget (10-27 board: a median 58% of
    # the largest request), so only a checkpoint, triggered by the rest of the context, ever drops it. "segment"
    # counts older replayed reasoning against the budget.
    if value == "segment" and context != "clm" or value == "all" and context not in ("clm", "append"):
        raise ConfigError(f"{REASONING_ENV}={value} needs model-managed context (clm)")
    if context == "append" and value not in ("all", "none"):  # append never edits its history: all or nothing
        raise ConfigError(f"{CONTEXT_ENV}=append needs {REASONING_ENV}=all or none")
    return value


def _clm_profile(environ: Mapping[str, str]) -> dict:
    """AETHER_CORE_CLM_PROFILE: "core" (default) keeps Core's CLM; "meta" applies Meta's published defaults
    (clm_settings.META_PROFILE). The meta profile fixes its own checkpoint policy, so setting both is refused."""
    profile = _choice(environ, "AETHER_CORE_CLM_PROFILE", CLM_PROFILES, "core")
    if profile == "core":
        return {"checkpoint_policy": _choice(environ, CHECKPOINT_POLICY_ENV, CHECKPOINT_POLICIES, "summary")}
    if environ.get(CHECKPOINT_POLICY_ENV, "").strip():
        raise ConfigError(f"AETHER_CORE_CLM_PROFILE=meta sets its own checkpoint policy; unset {CHECKPOINT_POLICY_ENV}")
    if environ.get(CONTEXT_ENV, "").strip() != "clm":
        raise ConfigError("AETHER_CORE_CLM_PROFILE=meta needs AETHER_CORE_CONTEXT=clm")
    return dict(META_PROFILE)


def _budget(environ: Mapping[str, str]) -> dict:
    """The editable-context budget, sized to the model rather than fixed (M1 b0, 2026-10-28: at 32000 a long-window
    model was urged to condense 54K to 4K at 658 s, dropping 25K of replayed reasoning and the evidence against its
    open hypothesis). The kept window after a checkpoint scales with it (a quarter, at least the 8000 default)."""
    raw = environ.get(BUDGET_ENV, "").strip()
    if not raw:
        return {}
    if not raw.isdigit() or int(raw) < 16_000:
        raise ConfigError(f"{BUDGET_ENV} must be an integer number of tokens >= 16000")
    return {"budget_tokens": int(raw), "keep_recent_tokens": max(8_000, int(raw) // 4)}


def _calls(environ: Mapping[str, str]) -> str:
    return _choice(environ, CALLS_ENV, CALLS_MODES, "one")


def _parallel_reads(environ: Mapping[str, str]) -> bool:
    return _choice(environ, PARALLEL_ENV, REPL_MODES, "off") == "on"


def _window(environ: Mapping[str, str]) -> int | None:
    """AETHER_CORE_CONTEXT_WINDOW: the provider's context window in tokens, needed by context "append" (no default:
    a guessed window would set every cut threshold wrong)."""
    raw = environ.get("AETHER_CORE_CONTEXT_WINDOW", "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise ConfigError(f"AETHER_CORE_CONTEXT_WINDOW must be a token count, got {raw!r}")
    return int(raw)
