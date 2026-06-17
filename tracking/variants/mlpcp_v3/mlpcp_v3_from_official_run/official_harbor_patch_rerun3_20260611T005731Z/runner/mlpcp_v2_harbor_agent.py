"""Harbor custom agent that runs MLPCP v2 host-side against task containers."""

from __future__ import annotations

import json
import os

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from runner.mlpcp_v2.execute_plan import ExecutePlanPolicy
from runner.mlpcp_v2.model_loop import ModelLoopConfig
from runner.mlpcp_v2_harbor_host import HarborHostRunner



def _json_safe(value):
    """Recursively convert MLPCP result objects into JSON-safe data.

    This prevents Harbor exceptions when result payloads contain dataclasses,
    enums, FinalizationDecision objects, References, or other objects with
    to_dict methods.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if hasattr(value, "to_dict"):
        try:
            return _json_safe(value.to_dict())
        except Exception:
            pass

    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int, float, bool)):
        return value.value

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    try:
        import dataclasses
        if dataclasses.is_dataclass(value):
            return _json_safe(dataclasses.asdict(value))
    except Exception:
        pass

    return str(value)



class MLPCPV2HarborAgent(BaseAgent):
    """Run the imported MLPCP variant inside Harbor-managed workspaces."""

    def __init__(
        self,
        *args,
        
        raw_bash_timeout_seconds: int = 60,
        deployment_name: str = "gpt-5.4-mini",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._raw_bash_timeout_seconds = int(raw_bash_timeout_seconds)
        self._deployment_name = deployment_name

    @staticmethod
    def name() -> str:
        return "mlpcp-v2-harbor"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.exec(command="pwd", cwd=None, timeout_sec=10)

    def _validate_azure_env(self) -> None:
        endpoint = (
            os.environ.get("AZURE_OPENAI_ENDPOINT")
            or os.environ.get("EVAL_SUITE_WORKER_AZURE_OPENAI_ENDPOINT")
            or os.environ.get("EVAL_SUITE_HEAD_AZURE_OPENAI_ENDPOINT")
        )
        api_key = (
            os.environ.get("AZURE_OPENAI_GPT54_MINI_KEY")
            or os.environ.get("AZURE_OPENAI_GPT53_CODEX_KEY")
            or os.environ.get("AZURE_OPENAI_API_KEY")
            or os.environ.get("EVAL_SUITE_WORKER_AZURE_OPENAI_API_KEY")
            or os.environ.get("EVAL_SUITE_HEAD_AZURE_OPENAI_API_KEY")
        )
        api_version = (
            os.environ.get("AZURE_OPENAI_API_VERSION")
            or os.environ.get("EVAL_SUITE_WORKER_AZURE_OPENAI_API_VERSION")
            or os.environ.get("EVAL_SUITE_HEAD_AZURE_OPENAI_API_VERSION")
            or "2024-12-01-preview"
        )
        if not endpoint or not api_key:
            raise RuntimeError("Azure OpenAI endpoint/key env is missing for Harbor MLPCP execution.")
        os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
        os.environ["AZURE_OPENAI_API_VERSION"] = api_version
        if "5.3" in self._deployment_name or "codex" in self._deployment_name.lower():
            os.environ["AZURE_OPENAI_GPT53_CODEX_KEY"] = api_key
            os.environ["AZURE_OPENAI_GPT53_CODEX_DEPLOYMENT"] = self._deployment_name
        else:
            os.environ["AZURE_OPENAI_GPT54_MINI_KEY"] = api_key
            os.environ["AZURE_OPENAI_GPT54_MINI_DEPLOYMENT"] = self._deployment_name

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        self._validate_azure_env()
        workspace_root = self.logs_dir / "host_workspace"
        receipt_root = self.logs_dir / "host_receipts"
        runner = HarborHostRunner(
            environment=environment,
            run_id=environment.session_id,
            row_id=environment.session_id,
            workspace_root=workspace_root,
            receipt_root=receipt_root,
            model_config={"model_name": self._deployment_name, "deployment_name": self._deployment_name},
            loop_config=ModelLoopConfig(
                max_steps=int(os.environ.get("MLPCP_MAX_STEPS", "30")),
                stop_on_blocked_finalization=False,
            ),
            execute_policy=ExecutePlanPolicy(
                solver_visible_roots=["."],
                raw_bash_timeout_seconds=self._raw_bash_timeout_seconds,
            ),
        )
        result = await runner.run(instruction=instruction)
        result_path = self.logs_dir / "mlpcp_result.json"
        payload = _json_safe(result.to_dict())
        result_path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True), encoding="utf-8")
        context.metadata = {
            "mlpcp_status": payload.get("status"),
            "mlpcp_finalization": payload.get("finalization"),
            "mlpcp_result_path": str(result_path),
        }

        # During smoke/debug runs, preserve MLPCP diagnostic statuses in mlpcp_result.json
        # instead of converting them into Harbor RuntimeError exceptions. A true Python
        # exception before this point will still fail the trial naturally.
        if payload.get("status") in {None, ""}:
            raise RuntimeError("MLPCP v2 Harbor task produced no status.")


__all__ = ["MLPCPV2HarborAgent"]
