#!/usr/bin/env python3
"""Run MLPCP v2 inside a Harbor-managed workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_path(script_path: Path) -> None:
    repo_root = script_path.resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_bootstrap_path(Path(__file__))

from runner.model_client import make_azure_gpt54_mini_route_from_env
from runner.mlpcp_v2.execute_plan import ExecutePlanPolicy, ExecutePlanRuntime, ToolExecutionContext
from runner.mlpcp_v2.integration import NoModelIntegrationSession
from runner.mlpcp_v2.live_model import RepoModelClientBridge
from runner.mlpcp_v2.model_loop import MLPCPModelLoop, ModelLoopConfig, ModelLoopRunResult, ModelLoopStep
from runner.mlpcp_v2.verifier_critic import VerifierCriticRequest
from runner.model_client import make_model_client_from_route


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _build_policy(session: NoModelIntegrationSession, *, raw_bash_timeout_seconds: int) -> ExecutePlanPolicy:
    substrate = session.substrate_result
    verifier_candidates = (substrate.verifier_locator_report or {}).get("candidates", [])
    artifact_report = substrate.artifact_contract_report or {}
    visible_helpers = [
        str(candidate.get("id") or "").strip()
        for candidate in verifier_candidates
        if candidate.get("id")
    ]
    declared_visible_verifiers = [
        str(candidate.get("command") or "").strip()
        for candidate in verifier_candidates
        if candidate.get("command")
    ]
    allowed_output_paths = [
        str(candidate.get("path") or "").strip()
        for candidate in artifact_report.get("required_outputs", [])
        if candidate.get("path")
    ]
    return ExecutePlanPolicy(
        solver_visible_roots=["."],
        visible_helpers=_dedupe(visible_helpers),
        declared_visible_verifiers=_dedupe(declared_visible_verifiers),
        allowed_output_paths=_dedupe(allowed_output_paths),
        raw_bash_timeout_seconds=raw_bash_timeout_seconds,
        allow_verifier_oracle_side=False,
    )


def _run_loop(
    *,
    run_id: str,
    row_id: str,
    workspace_root: Path,
    task_prompt: str,
    task_prompt_path: Path,
    
    raw_bash_timeout_seconds: int,
) -> ModelLoopRunResult:
    session = NoModelIntegrationSession(
        run_id=run_id,
        row_id=row_id,
        workspace_root=workspace_root,
    )
    substrate = session.certify_substrate(task_prompt=task_prompt, task_prompt_path=task_prompt_path)
    policy = _build_policy(session, raw_bash_timeout_seconds=raw_bash_timeout_seconds)
    execute_runtime = ExecutePlanRuntime(
        ToolExecutionContext(
            run_id=run_id,
            row_id=row_id,
            workspace_root=workspace_root,
            receipt_store=session.receipt_store,
            memory_store=session.memory_store,
            capability_graph=session.capability_graph,
            policy=policy,
        )
    )
    model_route = make_azure_gpt54_mini_route_from_env(request_settings={"temperature": 0})
    repo_client = make_model_client_from_route(model_route)
    model_client = RepoModelClientBridge(
        repo_client=repo_client,
        completion_kwargs={"temperature": 0, "max_retries": 1},
    )
    loop = MLPCPModelLoop(
        session=session,
        model_client=model_client,
        execute_runtime=execute_runtime,
        config=ModelLoopConfig(max_steps=None),
    )

    steps: list[ModelLoopStep] = []
    try:
        contract = loop.request_success_contract(
            task_prompt=task_prompt,
            cockpit_context={
                "env_contract": substrate.env_contract.to_dict(),
                "artifact_contract_report": substrate.artifact_contract_report,
                "verifier_locator_report": substrate.verifier_locator_report,
            },
        )
        session.enter_execute()
        idx = 1
        while True:
            cockpit = session.build_cockpit(step=idx)
            exec_result = loop.run_execute_step(step_index=idx, cockpit=cockpit.to_dict())
            finalization = exec_result.finalization or session.evaluate_finalization()
            critic_result = loop.critic.review(
                VerifierCriticRequest(
                    run_id=session.run_id,
                    row_id=session.row_id,
                    capability_graph=session.capability_graph,
                    finalization_decision=finalization,
                )
            )
            steps.append(
                ModelLoopStep(
                    idx,
                    "EXECUTE",
                    execute_result=exec_result.to_dict(),
                    critic_result=critic_result.to_dict(),
                    cockpit_chars=cockpit.budget.get("chars") or cockpit.budget.get("char_count"),
                )
            )
            if finalization.allowed and critic_result.may_claim_complete:
                return ModelLoopRunResult(
                    session.run_id,
                    session.row_id,
                    "complete",
                    steps,
                    contract.to_dict(),
                    finalization.to_dict(),
                )
            if exec_result.status == "blocked":
                return ModelLoopRunResult(
                    session.run_id,
                    session.row_id,
                    "blocked",
                    steps,
                    contract.to_dict(),
                    finalization.to_dict(),
                )
            idx += 1
        return ModelLoopRunResult(
            session.run_id,
            session.row_id,
            "step_limit",
            steps,
            contract.to_dict(),
            session.evaluate_finalization().to_dict(),
        )
    except Exception as exc:
        return ModelLoopRunResult(session.run_id, session.row_id, "error", steps, error=str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", default="/app")
    parser.add_argument("--instruction-file", required=True)
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--row-id", required=True)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--raw-bash-timeout-seconds", type=int, default=60)
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    instruction_file = Path(args.instruction_file).resolve()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    task_prompt = instruction_file.read_text(encoding="utf-8")
    result = _run_loop(
        run_id=args.run_id,
        row_id=args.row_id,
        workspace_root=workspace_root,
        task_prompt=task_prompt,
        task_prompt_path=instruction_file,
        raw_bash_timeout_seconds=args.raw_bash_timeout_seconds,
    )
    result_path = artifacts_dir / "result.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0 if result.status == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
