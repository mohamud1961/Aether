"""Core run configuration and the loop's fixed limits (split from loop.py, module cap)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .clm import ClmSettings
from .env import CONTROL_DIR, Environment
from .oversight import ReviewPlan


MAX_OUTPUT_TOKENS = 16_384  # was 32_768; see CoreConfig.max_output_tokens
# A turn the output limit cuts off before any tool call is almost never followed by action at the same effort:
# in the archived rows 30 of 32 such turns produced nothing, and V2 dna-assembly lost 550-900 s of each row to
# two or three in a row. The next turn runs at low effort, to act on the reasoning it already has.
AFTER_CUT = {"reasoning_effort": "low"}
# V3: 3 of 4 low-effort turns acted within 25 s (under 2k output tokens); one still reasoned to 32k (265 s).
# Its output cap bounds that case to a quarter of the time.
AFTER_CUT_MAX_TOKENS = 8_192
CONTEXT_MODES = ("project", "clm", "append")
VERIFIER_ROLE = "verifier"  # the call-log role of the one independent finish check (see verify)


@dataclass(frozen=True)
class CoreConfig:
    context: str = "project"
    repl: bool = False
    images: bool = False
    image_fidelity: str = "standard"  # "original": full-size images at detail "original" (AETHER_CORE_IMAGE_FIDELITY)
    reviews: ReviewPlan = ReviewPlan()
    clm: ClmSettings = field(default_factory=ClmSettings)
    control_dir: str = CONTROL_DIR  # where terminals and the REPL keep their files in the sandbox
    make_clone: Callable[[Environment], Awaitable[Any]] | None = None  # tests inject a clone; default docker
    parallel_reads: bool = False  # opt-in: bounded contiguous read_file batches only
    toolset: str = "full"  # minimal: terminal, CLM history recall, finish, and optional terminal_wait; python (B18):
    # the REPL and finish only, with bash()/mcp() as library functions (repl_lib_src)
    verify: bool = False  # one independent check of the first finish, in a fresh context on a clone (see verify)
    self_check: bool = (
        False  # the self-check paragraph in the system prompt (tools.SELF_CHECK_DOC)
    )
    intent: bool = False  # every action tool takes the model's reason and expected result (see intent)
    fork: bool = False  # experiment instrument: at the first finish, matched continuations on clones (see fork)
    fork_arms: tuple[tuple[str, str], ...] = ()  # named fork arms (fork.load_arms); empty: B and C
    fork_keep: bool = False  # keep the first-finish checkpoint for a later resume (fork.keep; named arms only)
    # Run end: "keep" (the default) leaves the container as the agent left it, because a service the task needs
    # running is part of the delivered state (E0/E3: pypi-server and kv-store-grpc 0/2 under stop, 2/2 under keep),
    # and records what was still running in ``left_running``. The container is owned by the trial and removed after
    # grading, which is the cleanup. "stop" kills every process started in a terminal (the pre-E3 behaviour).
    end_processes: str = "keep"
    hygiene: str = "off"  # tools.HYGIENE_MODES: one delivery-hygiene line (on) or its placebo in the solver prompt
    state: bool = False  # run state: harness-run requirement checks, notes, finish re-check (see runstate)
    managed_facts: bool = False  # isolated state/environment treatment; not yet qualified as a default
    facts_pull: bool = False  # expose managed observations as files instead of pushed notes
    facts_v2: bool = False  # the verified state service instead: env block + one line per action (state_service)
    role: str = "worker"  # call-log role of this run's own turns; VERIFIER_ROLE for the verifier's run
    record: bool = False  # the harness's record of the model's own command results, its facts and finish re-run (record)
    record_measure: bool = False  # the record also compares each check's printed results across file versions (record)
    record_paths: bool = False  # the record states only task-named paths that do not exist yet (record)
    record_commands: bool = False  # ...and at the first finish the task-shown commands no command contained (record)
    finish_hold: str = "off"  # "neutral": the first finish is held once with time left and no facts (control arm)
    browser: Any = None  # browser.Factory: a real browser in a sidecar on the task's network (browser); None = off
    browser_page_facts: bool = False  # C3: failed requests, dialogs, downloads in the browser state line (AETHER_CORE_BROWSER_PAGE_FACTS)
    browser_effects: bool = False  # C16: one line of fact after each browser action (AETHER_CORE_BROWSER_EFFECTS)
    browser_session: bool = False  # one browser kept open across browser calls (browser_session_src; AETHER_CORE_BROWSER=session)
    image_region: bool = False  # view_image may show part of an image at full resolution (image_region)
    image_compare: bool = False  # view two independently selected images in the same observation
    image_multi: bool = False  # view_image may name several files at once (AETHER_CORE_IMAGE_MULTI)
    # Reasoning effort for the request that first sees a newly attached image ("" = the run's own). 28 Oct: an
    # image-reading task went 0/3 at high and 2/3 valid at xhigh run-wide; this spends the extra effort only there.
    image_effort: str = ""
    env_brief: bool = False  # what the container provides (tools, packages, files), measured once, in the task (env_brief)
    start_copy: bool = False  # a copy of the working directory before the first action, named in the task (start_copy)
    task_at_first_observation: bool = False  # the task text once more, beside the first tool result (FD2, 10 Nov)
    stated_use: bool = False  # the task's own literal commands, run once when the work first exists (stated_use)
    working: str = "on"  # "lean": solver prompt without the three thoroughness lines (study arm)
    task_appendix_file: str = ""  # study arm: a file whose text follows the task in the first message (XL step-0 list)
    step0_file: str = ""  # study arm: JSON {question, answer}; the step-0 list as the model's own first turn (step0.py)
    agenda: str = "off"  # study arm: "on" = one no-tools call first; the model's own list of open points follows the task (agenda.py)
    start_note: str = "start"  # "late": start-copy note and state line wait for a changed start file (study arm)
    outside_witness: bool = False  # copies of /etc at the start and of outside originals at the first file-tool write (A21)
    outside_roots: tuple[str, ...] = ()  # with outside_witness: the roots copied at the start
    mcp_idempotency: bool = False  # an idempotency key in each MCP tool call's params._meta, reused on an identical retry after an unknown effect (A14)
    session_log: bool = False  # H10: append-only session log (logs/session) a new controller can resume from
    check_versions: bool = False  # E15, trace only: workspace version per action from the state service
    state_view: bool = False  # with start_copy: a read-only command showing what changed since it (state_view)
    diffcheck: bool = False  # an executable check of the task's output, written from the task alone during the run (diffcheck)
    # Per-turn output ceiling. Azure admits a request against the token rate limit by prompt + this ceiling, so
    # an unused ceiling costs rate-limit headroom (mission 2026-10-28: 2910 Luna turns, p99.9 11k, max 17k).
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    rival: bool = False  # at the first finish, a fresh call writes the strongest rival answer, handed back once (rival)
    exec_check: bool = False  # ablation of rival: the first finish is handed back once asking to run the deliverable
    card: bool = False  # at the first finish, a fresh reading of the request alone is handed back once (card)
    card_probe: bool = False  # the card's reader also writes a script observing each item; Core runs it once (card)
    card_challenge: str = ""  # "challenge": read-only checks, raw output (card, CH1); "attack": clone checks (attack, CH2); "observe": recorded only; "forks": start observations (forks)
    open_issues: bool = False  # finish takes the model's open issues; listing any with time left returns it once
    evidence_presentation: str = "off"  # default-off CLM source history index; not a task correctness engine
    stable_facts: bool = False
    terminal_events: bool = False
    finish_settle: bool = False  # hold the first finish once if delivered files are still changing (finish_settle)
    finish_facts: bool = False  # first finish returns delivered-state facts once (finish_facts)
    mcp_servers: tuple = ()  # opt-in (AETHER_CORE_MCP): task-declared MCP servers exposed through the mcp tool
    skills_dir: str | None = None  # opt-in (AETHER_CORE_SKILLS): the task-declared skills directory to list at start
    env_map: bool = False  # opt-in: repositories and listening services, measured once at start (env_map)
    rehydrate: bool = False  # opt-in (E18 K2): after a checkpoint or provider compaction, changed files read again
    auto_wait: bool = False  # opt-in (auto_wait): a reply with no tool call while work runs = sleep until it finishes
    auto_wait_grace_s: float = 30.0  # auto_wait: a terminal command's blocking window cap (Unreal: 1)
    multi_edit: bool = False  # opt-in (AETHER_CORE_MULTI_EDIT): edit_file takes a list of edits (tool_variants)
    wait_cap_s: float = 0.0  # opt-in (AETHER_CORE_WAIT_CAP): a terminal/python call blocks at most this long; 0 = off
    shell_kit: bool = False  # opt-in: apply_patch/view_image/job/pyk/ctx as terminal commands (shellkit)
    completion_notices: bool = False  # opt-in: one line when a background terminal command finishes (completion_notice)
    terminal_result_delivery: bool = False  # opt-in: collect completed terminal output at a tool boundary
    workspace_brief: bool = False
    workspace_search: bool = False
    fast_process_scan: bool = False  # opt-in: single-process pending-terminal observer with shell fallback
    fast_mcp_wait: bool = False  # opt-in: bounded sandbox-side response observation
    append_policy: str = "core64"  # context "append": a name in context_append_policies.POLICIES
    context_window: int | None = None  # context "append": the provider's window in tokens (required; no default)
    keep_cut_outputs: bool = False  # opt-in evidence (D18): copy each cut terminal span next to the trace at run end
    task_repeat: int = 1  # study arm R2: the first task message given this many times (prompt repetition)

    def __post_init__(self) -> None:
        if self.toolset not in ("full", "minimal", "python", "codex"):
            raise ValueError("toolset must be full, minimal, python or codex")
        if self.task_repeat not in (1, 2, 3):
            raise ValueError("task_repeat must be 1, 2 or 3")
        if self.toolset == "codex" and self.repl:  # study arm CX: terminal + apply_patch (+ view_image), as Codex
            raise ValueError("codex toolset cannot expose: repl")
        if self.toolset == "python":
            conflicts = [name for name, enabled in (
                ("repl off", not self.repl), ("browser", self.browser is not None), ("terminal_events", self.terminal_events),
                ("workspace_search", self.workspace_search), ("verify", self.verify),
                ("path_lookup", self.evidence_presentation == "path_lookup"),
            ) if enabled]
            if conflicts:
                raise ValueError(f"python toolset cannot combine with: {', '.join(conflicts)}")
        if self.toolset == "minimal":
            conflicts = [
                name for name, enabled in (
                    ("repl", self.repl), ("images", self.images), ("browser", self.browser is not None),
                    ("mcp_servers", bool(self.mcp_servers)), ("state", self.state),
                    ("workspace_search", self.workspace_search),
                    ("path_lookup", self.evidence_presentation == "path_lookup"),
                ) if enabled
            ]
            if conflicts:
                raise ValueError(f"minimal toolset cannot expose: {', '.join(conflicts)}")
        if self.facts_pull and not self.managed_facts:
            raise ValueError("facts_pull requires managed_facts")
        if self.managed_facts and self.env_brief:
            raise ValueError("managed_facts and env_brief are alternative information channels")
        if self.context not in CONTEXT_MODES:
            raise ValueError(f"context must be one of {CONTEXT_MODES}")
        if self.context == "append":
            from .context_append_policies import POLICIES

            if self.clm.replay_reasoning not in ("all", "none"):
                raise ValueError("context 'append' replays reasoning 'all' or 'none' (it never edits its history)")

            if self.append_policy not in POLICIES:
                raise ValueError(f"append_policy must be one of {tuple(POLICIES)}")
            if not isinstance(self.context_window, int) or self.context_window < 16_000:
                raise ValueError("context 'append' needs the provider's context_window in tokens (>= 16000)")
        from .clm_settings import CHECKPOINT_POLICIES

        if self.clm.checkpoint_policy not in CHECKPOINT_POLICIES:
            raise ValueError(f"checkpoint_policy must be one of {CHECKPOINT_POLICIES}")
        if self.clm.checkpoint_policy != "summary" and self.context != "clm":
            raise ValueError("window checkpoint policy requires Core CLM history")
        from .evidence_context import CONTEXT_EVIDENCE_MODES

        if self.evidence_presentation not in CONTEXT_EVIDENCE_MODES:
            raise ValueError(f"evidence_presentation must be one of {CONTEXT_EVIDENCE_MODES}")
        if self.evidence_presentation != "off" and self.context != "clm":
            raise ValueError("evidence_presentation requires Core CLM history")
        if self.evidence_presentation != "off" and not self.clm.attest_original_history:
            raise ValueError("Evidence retrieval requires append-time original-history attestation")
        self.clm.check_request_limit(self.max_output_tokens)
