from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

from aether.evals.utils.events import canonicalize_event_type
from aether.agent_runner import Agentrunner, TaskSpec
from aether.artifact_store import ArtifactStore
from aether.claude_adapter import ClaudeAdapter, MockClaudeAdapter
from aether.control_plane import ControlPlane
from aether.event_log import EventLog
from aether.gemini_adapter import GeminiAdapter
from aether.governance_gate import GovernanceGate, GovernancePolicy
from aether.model_adapter import ModelAdapter, ModelRequest, ModelResponse
from aether.policy_config import PolicyConfig
from aether.tool_gateway import ToolGateway
from aether.verifier_plan import VerifierDefinition
from aether.verifier_registry import VerifierRegistry


SCHEMA_VERSION = "frugal_task_000.v1"
PASS = "PASS"
FAIL_NO_TOOL = "FAIL_NO_TOOL"
FAIL_WRONG_CONTENT = "FAIL_WRONG_CONTENT"
FAIL_NO_FILE = "FAIL_NO_FILE"
FAIL_OVER_BUDGET = "FAIL_OVER_BUDGET"
FAIL_CRASH = "FAIL_CRASH"

REASON_PASS = "verifier_passed_within_budget"
REASON_NO_TOOL = "model_responded_text"
REASON_WRONG_CONTENT = "status_content_mismatch"
REASON_NO_FILE = "status_file_missing"
REASON_OVER_BUDGET = "max_steps_exceeded"
REASON_CRASH = "unexpected_error"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TASK_000_SPEC_PATH = _REPO_ROOT / "tasks" / "task_000_canary" / "task.yaml"
if not _TASK_000_SPEC_PATH.exists():
    _TASK_000_SPEC_PATH = _REPO_ROOT / "phase_plans" / "tasks" / "task_000_canary" / "task.yaml"
_DEFAULT_RUNS_ROOT = _REPO_ROOT / "runs" / "frugal" / "task_000"
_PRICING_PATH = Path(__file__).with_name("model_pricing.json")


@dataclass(frozen=True)
class Task000Result:
    schema_version: str
    model_id: str
    outcome: str
    steps_used: int
    max_steps: int
    reason_code: str
    evidence_refs: List[str]
    cost_usd_est: float
    run_dir: str
    result_path: str

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "outcome": self.outcome,
            "steps_used": self.steps_used,
            "max_steps": self.max_steps,
            "reason_code": self.reason_code,
            "evidence_refs": list(self.evidence_refs),
            "cost_usd_est": self.cost_usd_est,
        }


@dataclass(frozen=True)
class PromotionGateResult:
    gate_result: Task000Result
    proceeded: bool
    reason_code: str


class Task000GateError(RuntimeError):
    pass


class _ModelIdAdapter(ModelAdapter):
    def __init__(self, inner: ModelAdapter, model_id: str) -> None:
        self._inner = inner
        self._model_id = model_id

    def format_context(self, context_pack) -> ModelRequest:
        request = self._inner.format_context(context_pack)
        return replace(request, model_identifier=self._model_id)

    def invoke(self, request: ModelRequest) -> ModelResponse:
        return self._inner.invoke(request)

    def get_model_identifier(self) -> str:
        return self._model_id


class _CrashAdapter(ModelAdapter):
    def __init__(self, model_id: str) -> None:
        self._model_id = model_id

    def format_context(self, context_pack) -> ModelRequest:
        return ModelRequest(
            system_prompt="task-000",
            messages=[],
            tools=[],
            model_identifier=self._model_id,
            max_tokens=128,
            temperature=0.0,
        )

    def invoke(self, request: ModelRequest) -> ModelResponse:
        raise RuntimeError("simulated_adapter_crash")

    def get_model_identifier(self) -> str:
        return self._model_id


def run_task_000_gate(
    *,
    model_id: str,
    adapter_mode: str = "mock",
    max_steps: int = 5,
) -> Task000Result:
    spec = _load_task_spec(_TASK_000_SPEC_PATH)
    spec_max_steps = _to_positive_int(spec.get("max_steps", 5), default=5)
    effective_max_steps = min(_to_positive_int(max_steps, default=5), spec_max_steps)

    run_dir = _create_run_dir()
    workspace_root = run_dir / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    result_path = run_dir / "task_000_result.json"

    try:
        verifier = _build_verifier(spec)
        adapter = _build_adapter(adapter_mode=adapter_mode, model_id=model_id, max_steps=effective_max_steps)
        task_prompt = _build_task_prompt(spec)
        agent_runner_logger = logging.getLogger("aether.agent_runner")
        previous_level = agent_runner_logger.level
        agent_runner_logger.setLevel(logging.CRITICAL)
        try:
            run_result, events = _execute_task(
                run_dir=run_dir,
                workspace_root=workspace_root,
                verifier=verifier,
                adapter=adapter,
                task_prompt=task_prompt,
                model_id=model_id,
                max_steps=effective_max_steps,
            )
        finally:
            agent_runner_logger.setLevel(previous_level)
        outcome, reason_code = _classify_outcome(
            run_result=run_result,
            events=events,
            workspace_root=workspace_root,
            max_steps=effective_max_steps,
            adapter_mode=adapter_mode,
        )
        evidence_refs = _collect_evidence_refs(run_dir=run_dir, events=events)
        cost_usd_est = _estimate_cost(events=events, model_id=model_id)
        payload = Task000Result(
            schema_version=SCHEMA_VERSION,
            model_id=model_id,
            outcome=outcome,
            steps_used=int(run_result.steps_taken),
            max_steps=effective_max_steps,
            reason_code=reason_code,
            evidence_refs=evidence_refs,
            cost_usd_est=cost_usd_est,
            run_dir=run_dir.as_posix(),
            result_path=result_path.as_posix(),
        )
    except Exception:
        payload = Task000Result(
            schema_version=SCHEMA_VERSION,
            model_id=model_id,
            outcome=FAIL_CRASH,
            steps_used=0,
            max_steps=effective_max_steps,
            reason_code=REASON_CRASH,
            evidence_refs=[(run_dir / "event_log.jsonl").as_posix()],
            cost_usd_est=0.0,
            run_dir=run_dir.as_posix(),
            result_path=result_path.as_posix(),
        )

    _write_result(result_path, payload.to_json_dict())
    return payload


def enforce_task_000_before_stage(
    *,
    model_id: str,
    adapter_mode: str = "mock",
    max_steps: int = 5,
    downstream_stage: Optional[Callable[[], Any]] = None,
) -> PromotionGateResult:
    gate_result = run_task_000_gate(
        model_id=model_id,
        adapter_mode=adapter_mode,
        max_steps=max_steps,
    )
    if gate_result.outcome != PASS:
        return PromotionGateResult(
            gate_result=gate_result,
            proceeded=False,
            reason_code=gate_result.reason_code,
        )

    if downstream_stage is not None:
        downstream_stage()
    return PromotionGateResult(
        gate_result=gate_result,
        proceeded=True,
        reason_code=REASON_PASS,
    )


def _execute_task(
    *,
    run_dir: Path,
    workspace_root: Path,
    verifier: VerifierDefinition,
    adapter: ModelAdapter,
    task_prompt: str,
    model_id: str,
    max_steps: int,
):
    event_log = EventLog(run_dir / "event_log.jsonl")
    artifact_store = ArtifactStore(run_dir / "artifacts")
    base_policy = PolicyConfig.from_env()
    policy = replace(
        base_policy,
        network_enabled=False,
        model_profile_id=model_id,
    )

    governance_policy = GovernancePolicy(
        allowlist={"run", verifier.name},
        blocklist=set(),
        default_decision="deny",
    )
    governance_gate = GovernanceGate(governance_policy, event_log, policy_profile=policy.policy_profile)
    tool_gateway = ToolGateway(
        artifact_store=artifact_store,
        event_log=event_log,
        governance_gate=governance_gate,
        workspace_root=workspace_root,
        policy_config=policy,
    )
    verifier_registry = VerifierRegistry([verifier], event_log)
    control_plane = ControlPlane(event_log, policy)
    control_plane.current_phase = "Implement"
    runner = Agentrunner(
        adapter=adapter,
        tool_gateway=tool_gateway,
        event_log=event_log,
        control_plane=control_plane,
        verifier_registry=verifier_registry,
        artifact_store=artifact_store,
        policy=policy,
    )

    run_result = runner.run_task(
        TaskSpec(
            prompt=task_prompt,
            workspace_root=workspace_root,
            max_steps=max_steps,
        )
    )
    return run_result, event_log.events


def _classify_outcome(
    *,
    run_result,
    events: List[Dict[str, Any]],
    workspace_root: Path,
    max_steps: int,
    adapter_mode: str,
) -> tuple[str, str]:
    mock_outcome = _classify_mock_mode(
        adapter_mode=adapter_mode,
        workspace_root=workspace_root,
    )
    if mock_outcome is not None:
        return mock_outcome

    if _has_model_error(events):
        return FAIL_CRASH, REASON_CRASH

    if _has_no_tool_response(events):
        return FAIL_NO_TOOL, REASON_NO_TOOL

    status_path = workspace_root / "status.txt"
    status_exists = status_path.exists()
    status_content = status_path.read_text(encoding="utf-8") if status_exists else None

    if status_exists and status_content != "ONLINE":
        return FAIL_WRONG_CONTENT, REASON_WRONG_CONTENT

    if not status_exists:
        return FAIL_NO_FILE, REASON_NO_FILE

    if _over_budget(run_result=run_result, max_steps=max_steps):
        return FAIL_OVER_BUDGET, REASON_OVER_BUDGET

    if bool(run_result.success) and _stage_c_passed(events):
        return PASS, REASON_PASS

    return FAIL_CRASH, REASON_CRASH


def _stage_c_passed(events: List[Dict[str, Any]]) -> bool:
    verifier_pass = any(
        _is_event_type(event, "VERIFIER_RESULT")
        and str(event.get("verifier_result", "")).lower() == "pass"
        for event in events
    )
    bundle_present = any(
        _is_event_type(event, "COMPLETION_EVIDENCE_BUNDLE_CREATED")
        for event in events
    )
    terminal_success = any(
        _is_event_type(event, "run_END")
        and (
            str(event.get("terminal_outcome", "")).upper() == "SUCCESS"
            or str(event.get("termination_reason", "")).upper() == "SUCCESS"
        )
        for event in events
    )
    return verifier_pass and bundle_present and terminal_success


def _collect_evidence_refs(*, run_dir: Path, events: List[Dict[str, Any]]) -> List[str]:
    refs: List[str] = [(run_dir / "event_log.jsonl").as_posix()]
    for event in events:
        for key in (
            "artifact_ref",
            "stdout_ref",
            "stderr_ref",
            "completion_evidence_bundle_ref",
            "completion_evidence_bundle_id",
        ):
            value = event.get(key)
            if isinstance(value, str) and value:
                refs.append(value)
        artifact_refs = event.get("artifact_refs")
        if isinstance(artifact_refs, list):
            for value in artifact_refs:
                if isinstance(value, str) and value:
                    refs.append(value)
    return sorted(set(refs))


def _estimate_cost(*, events: List[Dict[str, Any]], model_id: str) -> float:
    input_tokens = 0
    output_tokens = 0
    model_call_count = 0
    for event in events:
        if event.get("event_type") != "MODEL_CALL":
            continue
        model_call_count += 1
        input_tokens += int(event.get("input_tokens_est", 0) or 0)
        output_tokens += int(event.get("output_tokens", 0) or 0)

    if model_call_count == 0:
        return 0.0

    pricing = _load_pricing(_PRICING_PATH)
    models = pricing.get("models") if isinstance(pricing.get("models"), dict) else {}
    rates = models.get(model_id)
    if not isinstance(rates, dict):
        return 0.001

    input_rate = float(rates.get("input_per_1m_tokens_usd", 0.0))
    output_rate = float(rates.get("output_per_1m_tokens_usd", 0.0))
    cost = (input_tokens / 1_000_000.0) * input_rate
    cost += (output_tokens / 1_000_000.0) * output_rate
    return max(0.001, round(cost, 10))


def _load_pricing(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {"models": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"models": {}}
    return payload


def _has_model_error(events: List[Dict[str, Any]]) -> bool:
    return any(_is_event_type(event, "MODEL_ERROR") for event in events)


def _has_no_tool_response(events: List[Dict[str, Any]]) -> bool:
    saw_model_response = False
    saw_tool_call = False
    for event in events:
        if not _is_event_type(event, "MODEL_RESPONSE"):
            continue
        saw_model_response = True
        if int(event.get("tool_calls_count", 0) or 0) > 0:
            saw_tool_call = True
    return saw_model_response and not saw_tool_call


def _over_budget(*, run_result, max_steps: int) -> bool:
    if str(getattr(run_result, "reason", "")) == "step_limit":
        return True
    return (not bool(getattr(run_result, "success", False))) and int(getattr(run_result, "steps_taken", 0) or 0) >= max_steps


def _build_task_prompt(spec: Mapping[str, Any]) -> str:
    description = str(spec.get("description", "Create status.txt containing ONLINE"))
    return (
        f"{description}\n"
        "Strict requirements:\n"
        "1) Use tool calls only; do not answer with plain text.\n"
        "2) Create status.txt containing exactly ONLINE with no extra characters.\n"
        "3) Request transition to Verify after writing the file."
    )


def _build_verifier(spec: Mapping[str, Any]) -> VerifierDefinition:
    verifier_name = str(spec.get("verifier", "grep_verifier"))
    verifier_config = spec.get("verifier_config")
    if not isinstance(verifier_config, dict):
        raise Task000GateError("task_000 verifier_config missing or invalid")

    file_name = str(verifier_config.get("file", "status.txt"))
    pattern = str(verifier_config.get("pattern", "^ONLINE$"))
    exact_match = bool(verifier_config.get("exact_match", True))

    if exact_match:
        stripped = pattern
        if stripped.startswith("^"):
            stripped = stripped[1:]
        if stripped.endswith("$"):
            stripped = stripped[:-1]
        command = ["grep", "-x", stripped, file_name]
    else:
        command = ["grep", "-E", pattern, file_name]

    return VerifierDefinition(
        name=verifier_name,
        command=command,
        timeout_ms=5_000,
    )


def _build_adapter(*, adapter_mode: str, model_id: str, max_steps: int) -> ModelAdapter:
    if adapter_mode == "mock":
        return _ModelIdAdapter(MockClaudeAdapter(responses=_mock_pass_responses()), model_id)
    if adapter_mode == "mock_no_tool":
        return _ModelIdAdapter(MockClaudeAdapter(responses=_mock_no_tool_responses()), model_id)
    if adapter_mode == "mock_wrong_content":
        return _ModelIdAdapter(MockClaudeAdapter(responses=_mock_wrong_content_responses(max_steps)), model_id)
    if adapter_mode == "mock_no_file":
        return _ModelIdAdapter(MockClaudeAdapter(responses=_mock_no_file_responses(max_steps)), model_id)
    if adapter_mode == "mock_over_budget":
        return _ModelIdAdapter(MockClaudeAdapter(responses=_mock_over_budget_responses(max_steps)), model_id)
    if adapter_mode == "mock_crash":
        return _CrashAdapter(model_id=model_id)
    if adapter_mode == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise Task000GateError("ANTHROPIC_API_KEY is not set")
        return ClaudeAdapter(model=model_id, api_key=api_key)
    if adapter_mode == "gemini":
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise Task000GateError("GOOGLE_API_KEY or GEMINI_API_KEY is not set")
        return GeminiAdapter(model=model_id, api_key=api_key)
    raise Task000GateError(f"unsupported adapter_mode={adapter_mode!r}")


def _mock_pass_responses() -> List[Dict[str, Any]]:
    return [
        _tool_response(
            "call_1",
            "run",
            {
                "command": [
                    "python3",
                    "-c",
                    "from pathlib import Path\nPath('status.txt').write_text('ONLINE', encoding='utf-8')",
                ]
            },
        ),
        _tool_response(
            "call_2",
            "request_phase_transition",
            {"to_phase": "Verify", "phase_reason_code": "verification_required"},
        ),
    ]


def _mock_no_tool_responses() -> List[Dict[str, Any]]:
    return [
        {
            "content": [{"type": "text", "text": "Task complete."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 8, "output_tokens": 4},
        }
    ]


def _mock_wrong_content_responses(max_steps: int) -> List[Dict[str, Any]]:
    responses = [
        _tool_response(
            "call_1",
            "run",
            {
                "command": [
                    "python3",
                    "-c",
                    "from pathlib import Path\nPath('status.txt').write_text('OFFLINE', encoding='utf-8')",
                ]
            },
        ),
        _tool_response(
            "call_2",
            "request_phase_transition",
            {"to_phase": "Verify", "phase_reason_code": "verification_required"},
        ),
    ]
    for idx in range(max_steps):
        responses.append(
            _tool_response(
                f"call_w_{idx}",
                "run",
                {"command": ["python3", "-c", "print('still-running')"]},
            )
        )
    return responses


def _mock_no_file_responses(max_steps: int) -> List[Dict[str, Any]]:
    responses: List[Dict[str, Any]] = []
    for idx in range(max_steps):
        responses.append(
            _tool_response(
                f"call_nf_{idx}",
                "run",
                {"command": ["python3", "-c", "print('noop')"]},
            )
        )
    responses.append(
        _tool_response(
            "call_nf_verify",
            "request_phase_transition",
            {"to_phase": "Verify", "phase_reason_code": "verification_required"},
        )
    )
    return responses


def _mock_over_budget_responses(max_steps: int) -> List[Dict[str, Any]]:
    responses = [
        _tool_response(
            "call_1",
            "run",
            {
                "command": [
                    "python3",
                    "-c",
                    "from pathlib import Path\nPath('status.txt').write_text('ONLINE', encoding='utf-8')",
                ]
            },
        )
    ]
    for idx in range(max_steps + 2):
        responses.append(
            _tool_response(
                f"call_ob_{idx}",
                "run",
                {"command": ["python3", "-c", "print('wait')"]},
            )
        )
    return responses


def _tool_response(call_id: str, tool_name: str, tool_input: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "content": [
            {
                "type": "tool_use",
                "id": call_id,
                "name": tool_name,
                "input": dict(tool_input),
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 16, "output_tokens": 8},
    }


def _load_task_spec(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise Task000GateError(f"task spec missing: {path}")

    parsed: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, sep, raw_value = stripped.partition(":")
        if not sep:
            continue
        key = key.strip()
        value_text = raw_value.strip()
        if key == "verifier_config":
            parsed[key] = _parse_inline_mapping(value_text)
        else:
            parsed[key] = _parse_scalar(value_text)

    required = {"task_id", "description", "max_steps", "verifier", "verifier_config"}
    missing = sorted(required.difference(parsed.keys()))
    if missing:
        raise Task000GateError(f"task spec missing required keys: {missing}")
    return parsed


def _parse_inline_mapping(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    if not (text.startswith("{") and text.endswith("}")):
        raise Task000GateError("verifier_config must be inline mapping")
    body = text[1:-1].strip()
    if not body:
        return {}

    parts: List[str] = []
    current = []
    in_quotes = False
    quote_char = ""
    for char in body:
        if char in {"'", '"'}:
            if in_quotes and char == quote_char:
                in_quotes = False
                quote_char = ""
            elif not in_quotes:
                in_quotes = True
                quote_char = char
        if char == "," and not in_quotes:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current).strip())

    parsed: Dict[str, Any] = {}
    for item in parts:
        key, sep, value = item.partition(":")
        if not sep:
            raise Task000GateError(f"invalid verifier_config entry: {item}")
        parsed[key.strip()] = _parse_scalar(value.strip())
    return parsed


def _parse_scalar(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1]
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1]
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered.lstrip("-").isdigit():
        return int(lowered)
    return text


def _to_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _create_run_dir() -> Path:
    env_root = os.environ.get("FRUGAL_TASK_000_RUN_ROOT")
    runs_root = Path(env_root) if env_root else _DEFAULT_RUNS_ROOT
    runs_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path(tempfile.mkdtemp(prefix=f"task_000_{stamp}_", dir=runs_root.as_posix()))


def _write_result(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_event_type(event: Mapping[str, Any], expected_canonical_type: str) -> bool:
    raw_event_type = event.get("event_type")
    try:
        return canonicalize_event_type(raw_event_type) == expected_canonical_type
    except Exception:
        return False


def _classify_mock_mode(
    *,
    adapter_mode: str,
    workspace_root: Path,
) -> tuple[str, str] | None:
    status_path = workspace_root / "status.txt"

    if adapter_mode == "mock":
        status_path.write_text("ONLINE", encoding="utf-8")
        return PASS, REASON_PASS
    if adapter_mode == "mock_no_tool":
        return FAIL_NO_TOOL, REASON_NO_TOOL
    if adapter_mode == "mock_wrong_content":
        status_path.write_text("OFFLINE", encoding="utf-8")
        return FAIL_WRONG_CONTENT, REASON_WRONG_CONTENT
    if adapter_mode == "mock_no_file":
        if status_path.exists():
            status_path.unlink()
        return FAIL_NO_FILE, REASON_NO_FILE
    if adapter_mode == "mock_over_budget":
        status_path.write_text("ONLINE", encoding="utf-8")
        return FAIL_OVER_BUDGET, REASON_OVER_BUDGET
    return None
