from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .artifact_store import ArtifactStore
from .enum_registry import EnumRegistry, load_enum_registry
from .event_log import EventLog


@dataclass(frozen=True)
class TaskListItem:
    item_id: str
    title: str
    status: str
    notes_artifact_id: Optional[str]


@dataclass(frozen=True)
class TaskList:
    task_list_id: str
    items: List[TaskListItem]


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    intent: str
    expected_outputs: List[str]
    required_tool_categories: List[str]
    required_receipt_fingerprints: List[str]
    required_verifiers: List[str]
    constraints_ref: Optional[str] = None


@dataclass(frozen=True)
class ImplementationPlan:
    plan_id: str
    plan_version_id: int
    status: str
    steps: List[PlanStep]
    plan_constraints: Dict[str, Any]
    intent_contract_ref: str
    completion_contract_ref: str


def persist_plan_defined(
    *,
    task_list: TaskList,
    plan: ImplementationPlan,
    artifact_store: ArtifactStore,
    event_log: EventLog,
    timestamp: str,
    cwd: str,
) -> Dict[str, str]:
    payload = {
        "task_list": {
            "task_list_id": task_list.task_list_id,
            "items": [asdict(item) for item in task_list.items],
        },
        "implementation_plan": {
            "plan_id": plan.plan_id,
            "plan_version_id": plan.plan_version_id,
            "status": plan.status,
            "steps": [asdict(step) for step in plan.steps],
            "plan_constraints": plan.plan_constraints,
            "intent_contract_ref": plan.intent_contract_ref,
            "completion_contract_ref": plan.completion_contract_ref,
        },
    }
    artifact_ref, content_hash = artifact_store.write_json_canonical(payload)
    event_log.append_event(
        {
            "event_type": "PLAN_DEFINED",
            "timestamp": timestamp,
            "cwd": cwd,
            "plan_id": plan.plan_id,
            "plan_version_id": plan.plan_version_id,
            "status": plan.status,
            "task_list_id": task_list.task_list_id,
            "artifact_refs": [artifact_ref.artifact_id],
            "content_hash": content_hash,
        }
    )
    return {
        "artifact_id": artifact_ref.artifact_id,
        "content_hash": content_hash,
    }


@dataclass
class PlanLifecycle:
    plan: ImplementationPlan
    task_list: TaskList
    enum_registry: EnumRegistry = field(default_factory=load_enum_registry)

    def change_status(
        self,
        *,
        to_status: str,
        source: str,
        timestamp: str,
        cwd: str,
        event_log: EventLog,
    ) -> None:
        if not self.enum_registry.validate_enum("plan_status", to_status):
            raise ValueError(f"invalid_plan_status:{to_status}")
        if source == "model_output" and to_status in {"APPROVED", "COMPLETE"}:
            event_log.append_event(
                {
                    "event_type": "POLICY_VIOLATION",
                    "timestamp": timestamp,
                    "cwd": cwd,
                    "violation_code": "OVERRIDE_ATTEMPT",
                    "detail": "model_self_approval_blocked",
                }
            )
            raise PermissionError("model_self_approval_blocked")

        from_status = self.plan.status
        self.plan = ImplementationPlan(
            plan_id=self.plan.plan_id,
            plan_version_id=self.plan.plan_version_id,
            status=to_status,
            steps=self.plan.steps,
            plan_constraints=self.plan.plan_constraints,
            intent_contract_ref=self.plan.intent_contract_ref,
            completion_contract_ref=self.plan.completion_contract_ref,
        )
        event_log.append_event(
            {
                "event_type": "PLAN_STATUS_CHANGED",
                "timestamp": timestamp,
                "cwd": cwd,
                "plan_id": self.plan.plan_id,
                "plan_version_id": self.plan.plan_version_id,
                "from_status": from_status,
                "to_status": to_status,
                "source": source,
                "status": to_status,
            }
        )

    def emit_step_status(
        self,
        *,
        step_id: str,
        status: str,
        verifier_ids: Optional[List[str]],
        timestamp: str,
        cwd: str,
        event_log: EventLog,
    ) -> None:
        if not self.enum_registry.validate_enum("plan_status", status):
            raise ValueError(f"invalid_task_status:{status}")
        event_log.append_event(
            {
                "event_type": "PLAN_STEP_STATUS",
                "timestamp": timestamp,
                "cwd": cwd,
                "plan_id": self.plan.plan_id,
                "plan_version_id": self.plan.plan_version_id,
                "plan_step_id": step_id,
                "status": status,
                "verifier_ids": verifier_ids or [],
            }
        )

    def record_plan_mismatch(
        self,
        *,
        tool_name: str,
        tool_args: Dict[str, Any],
        timestamp: str,
        cwd: str,
        event_log: EventLog,
    ) -> None:
        event_log.append_event(
            {
                "event_type": "PLAN_MISMATCH",
                "timestamp": timestamp,
                "cwd": cwd,
                "plan_id": self.plan.plan_id,
                "plan_version_id": self.plan.plan_version_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            }
        )

    def create_plan_update(
        self,
        *,
        updated_steps: List[PlanStep],
        reason_code: str,
        timestamp: str,
        cwd: str,
        event_log: EventLog,
        artifact_store: ArtifactStore,
    ) -> None:
        from_version = self.plan.plan_version_id
        to_version = from_version + 1
        if to_version <= from_version:
            raise ValueError("plan_version_id must be monotonic")

        old_steps = [asdict(step) for step in self.plan.steps]
        new_steps = [asdict(step) for step in updated_steps]
        diff_payload = {
            "plan_id": self.plan.plan_id,
            "from_plan_version_id": from_version,
            "to_plan_version_id": to_version,
            "update_reason_code": reason_code,
            "changes": {
                "old_steps": old_steps,
                "new_steps": new_steps,
            },
        }
        diff_ref, diff_content_hash = artifact_store.write_json_canonical(diff_payload)

        self.plan = ImplementationPlan(
            plan_id=self.plan.plan_id,
            plan_version_id=to_version,
            status="DRAFT",
            steps=updated_steps,
            plan_constraints=self.plan.plan_constraints,
            intent_contract_ref=self.plan.intent_contract_ref,
            completion_contract_ref=self.plan.completion_contract_ref,
        )
        event_log.append_event(
            {
                "event_type": "PLAN_UPDATE",
                "timestamp": timestamp,
                "cwd": cwd,
                "plan_id": self.plan.plan_id,
                "from_plan_version_id": from_version,
                "to_plan_version_id": to_version,
                "diff_artifact_id": diff_ref.artifact_id,
                "diff_content_hash": diff_content_hash,
                "update_reason_code": reason_code,
                "artifact_refs": [diff_ref.artifact_id],
            }
        )


def default_task_and_plan(
    *,
    intent_contract_ref: str,
    completion_contract_ref: str,
    task_item_titles: Optional[List[str]] = None,
) -> tuple[TaskList, ImplementationPlan]:
    normalized_titles: List[str] = []
    seen_titles: set[str] = set()
    for raw_title in task_item_titles or []:
        title = str(raw_title).strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        normalized_titles.append(title)

    if not normalized_titles:
        normalized_titles = ["Complete requested task"]

    task_list = TaskList(
        task_list_id=f"tasklist:{intent_contract_ref[:12]}",
        items=[
            TaskListItem(
                item_id=f"item-{index + 1}",
                title=title,
                status="TODO",
                notes_artifact_id=None,
            )
            for index, title in enumerate(normalized_titles)
        ],
    )
    plan = ImplementationPlan(
        plan_id=f"plan:{intent_contract_ref[:12]}",
        plan_version_id=1,
        status="DRAFT",
        steps=[
            PlanStep(
                step_id="step-1",
                intent="Implement the requested task in the workspace.",
                expected_outputs=["Code changes", "Verification evidence"],
                required_tool_categories=["FILESYSTEM", "EXECUTION", "VERIFIER"],
                required_receipt_fingerprints=[],
                required_verifiers=[],
            )
        ],
        plan_constraints={"no_network": True},
        intent_contract_ref=intent_contract_ref,
        completion_contract_ref=completion_contract_ref,
    )
    return task_list, plan
