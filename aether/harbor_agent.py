"""Thin installed Harbor adapter for Aether's single production runtime.

Harbor owns benchmark staging, environment lifecycle and official grading.
This adapter only bridges a Harbor task environment into Aether and returns
control to Harbor.  It performs no board scheduling, retries or grading.
"""
from __future__ import annotations

from pathlib import Path
import time
from typing import Any

_HARBOR_IMPORT_ERROR: BaseException | None = None
try:
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
except ModuleNotFoundError as exc:  # source/unit-test surfaces may omit Harbor
    _HARBOR_IMPORT_ERROR = exc

    class BaseAgent:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs
            raise RuntimeError(
                "Harbor is not installed on this execution surface; "
                "AetherHarborAgent cannot be instantiated"
            ) from _HARBOR_IMPORT_ERROR

    BaseEnvironment = Any  # type: ignore[assignment,misc]
    AgentContext = Any  # type: ignore[assignment,misc]

from .environment_extensions import normalize_mcp_servers
from .harbor_runtime import discover_harbor_workspace, run_harbor_aether


class AetherHarborAgent(BaseAgent):
    """Installed Harbor ``BaseAgent`` wrapper around Aether PCR."""

    SUPPORTS_ATIF = True
    SUPPORTS_WINDOWS = False

    @staticmethod
    def name() -> str:
        return "aether"

    def version(self) -> str:
        return "s3-harbor-v1"

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        extra_env: dict[str, str] | None = None,
        agent_timeout_sec: float | None = None,
        **kwargs: Any,
    ) -> None:
        if _HARBOR_IMPORT_ERROR is not None:
            raise RuntimeError(
                "Harbor import unavailable; install the qualified Harbor runtime "
                "before constructing AetherHarborAgent"
            ) from _HARBOR_IMPORT_ERROR
        super().__init__(
            logs_dir=logs_dir,
            model_name=model_name,
            extra_env=extra_env,
            **kwargs,
        )
        self._extra_env = dict(extra_env or {})
        self._agent_timeout_sec = agent_timeout_sec
        self._mcp_servers = normalize_mcp_servers(getattr(self, "mcp_servers", ()))
        self._setup_workspace: dict[str, Any] | None = None

    async def setup(self, environment: BaseEnvironment) -> None:
        """Discover execution facts only; never contact a model provider."""
        facts = await discover_harbor_workspace(environment)
        self._setup_workspace = {
            "pwd": facts.pwd,
            "git_root": facts.git_root,
            "workspace_root": facts.workspace_root,
            "existing_candidates": list(facts.existing_candidates),
        }

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        run_started_monotonic = time.monotonic()
        metadata = dict(getattr(context, "metadata", None) or {})
        metadata["aether_adapter"] = {
            "name": self.name(),
            "version": self.version(),
            "supports_atif": True,
            "setup_workspace": dict(self._setup_workspace or {}),
            "environment_extensions": {
                "mcp_server_count": len(self._mcp_servers),
                "mcp_servers": [dict(row) for row in self._mcp_servers],
            },
        }
        context.metadata = metadata
        await run_harbor_aether(
            environment=environment,
            context=context,
            instruction=instruction,
            logs_dir=Path(self.logs_dir),
            mcp_servers=self._mcp_servers,
            agent_timeout_sec=self._agent_timeout_sec,
            run_started_monotonic=run_started_monotonic,
        )


__all__ = ["AetherHarborAgent"]
