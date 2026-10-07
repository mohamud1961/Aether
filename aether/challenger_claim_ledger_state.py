"""Task-local CHALLENGER state and durable serialization."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .challenger_claim_types import (
    ActionKind,
    ActionObservation,
    CardKind,
    CheckKind,
    CheckOrigin,
    CheckResult,
    ClaimCard,
    CompletionCard,
    CriterionClaim,
    DiagnosisCard,
    Hypothesis,
    LEDGER_SCHEMA,
    LedgerIdentity,
    MAX_VERIFY_REPAIR_CYCLES,
    ProgressClaimCard,
    QuestionnaireRound,
    QUESTIONNAIRE_SCHEMA,
    RepairCycleLimitError,
    RunnableCheck,
    TriggerEvent,
    TriggerKind,
    DEFAULT_MATERIAL_ACTION_INTERVAL,
    DEFAULT_NO_CHANGE_ACTIONS,
)


class TaskLocalClaimLedger:
    """Single-writer ledger intended for one task/run-private state directory."""

    def __init__(
        self,
        identity: LedgerIdentity,
        *,
        no_change_actions: int = DEFAULT_NO_CHANGE_ACTIONS,
        material_action_interval: int = DEFAULT_MATERIAL_ACTION_INTERVAL,
        max_cycles: int = MAX_VERIFY_REPAIR_CYCLES,
    ) -> None:
        if no_change_actions < 1 or material_action_interval < 1 or max_cycles < 1:
            raise ValueError("trigger thresholds and the cycle bound must be positive")
        self.max_cycles = max_cycles
        self.identity = identity
        self.no_change_threshold = no_change_actions
        self.material_action_interval = material_action_interval
        self.accepted_action_count = 0
        self.material_action_count = 0
        self.no_change_action_count = 0
        self.last_state_fingerprint = ""
        self.first_production_write_seen = False
        self.seen_signatures: set[str] = set()
        self.fired_repeat_signatures: set[str] = set()
        self.fired_failure_action_ids: set[str] = set()
        self.trigger_events: list[TriggerEvent] = []
        self.cards: list[ClaimCard] = []
        self.check_results: list[CheckResult] = []
        self.questionnaire_receipts: list[dict[str, Any]] = []
        self.action_receipts: list[dict[str, Any]] = []
        self.verify_repair_cycles = 0

    def observe_action(self, observation: ActionObservation) -> tuple[TriggerEvent, ...]:
        if not observation.accepted:
            return ()
        known_claim_ids = {card.card_id for card in self.cards}
        unknown_claims = set(observation.contradicted_claim_ids) - known_claim_ids
        if unknown_claims:
            raise ValueError("contradiction trigger refers to a claim outside this task ledger")
        self.accepted_action_count += 1
        ordinal = self.accepted_action_count
        events: list[TriggerEvent] = []

        if self.last_state_fingerprint and observation.state_fingerprint == self.last_state_fingerprint:
            self.no_change_action_count += 1
        else:
            self.no_change_action_count = 0
        state_changed = observation.state_fingerprint != self.last_state_fingerprint
        self.last_state_fingerprint = observation.state_fingerprint

        production_write = any(not write.is_scratch for write in observation.writes)
        if production_write and not self.first_production_write_seen:
            self.first_production_write_seen = True
            events.append(self._event(TriggerKind.FIRST_PRODUCTION_WRITE, ordinal, ("first_non_scratch_write",)))

        stuck_reasons: list[str] = []
        signature = observation.repeat_signature.strip()
        if signature and signature in self.seen_signatures and signature not in self.fired_repeat_signatures:
            self.fired_repeat_signatures.add(signature)
            stuck_reasons.append("repeat_signature")
        if signature:
            self.seen_signatures.add(signature)
        if observation.unexpected_failure and observation.action_id not in self.fired_failure_action_ids:
            self.fired_failure_action_ids.add(observation.action_id)
            stuck_reasons.append("unexpected_failure")
        if observation.contradicted_claim_ids:
            stuck_reasons.append("claim_contradicted")
        if self.no_change_action_count == self.no_change_threshold:
            stuck_reasons.append("no_task_state_change_threshold")
        if stuck_reasons:
            events.append(self._event(TriggerKind.STUCK_OR_CONTRADICTED, ordinal, tuple(stuck_reasons)))

        if observation.material:
            self.material_action_count += 1
            if self.material_action_count % self.material_action_interval == 0:
                events.append(self._event(
                    TriggerKind.PROGRESS_MILESTONE,
                    ordinal,
                    (f"material_action_{self.material_action_count}",),
                ))

        if observation.finish_intent:
            events.append(self._event(TriggerKind.FINISH_INTENT, ordinal, ("finish_intent",)))

        self.trigger_events.extend(events)
        if state_changed:
            self.no_change_action_count = 0
            self.fired_repeat_signatures.clear()
        return tuple(events)

    def force_trigger(self, kind: TriggerKind, reasons: tuple[str, ...]) -> TriggerEvent:
        """Record a runtime-owned trigger (e.g. the T1 action-count fallback) for the current ordinal."""
        base = self._event(kind, self.accepted_action_count, reasons)
        taken = {existing.trigger_id for existing in self.trigger_events}
        n = 1
        while f"{base.trigger_id}:forced{n}" in taken:
            n += 1
        event = TriggerEvent(f"{base.trigger_id}:forced{n}", base.kind, base.action_ordinal, reasons)
        self.trigger_events.append(event)
        return event

    def _event(self, kind: TriggerKind, ordinal: int, reasons: tuple[str, ...]) -> TriggerEvent:
        event = TriggerEvent(f"trigger:{ordinal}:{kind.value}", kind, ordinal, reasons)
        return event

    def record_card(self, card: ClaimCard) -> None:
        if any(existing.card_id == card.card_id for existing in self.cards):
            raise ValueError(f"duplicate claim card id: {card.card_id}")
        trigger = next((event for event in self.trigger_events if event.trigger_id == card.trigger_id), None)
        if trigger is None:
            raise ValueError("claim card trigger does not belong to this task ledger")
        allowed_triggers = {
            CardKind.DIAGNOSIS: {TriggerKind.FIRST_PRODUCTION_WRITE, TriggerKind.STUCK_OR_CONTRADICTED},
            CardKind.PROGRESS: {TriggerKind.PROGRESS_MILESTONE},
            CardKind.COMPLETION: {TriggerKind.FINISH_INTENT},
        }
        if trigger.kind not in allowed_triggers[card.kind]:
            raise ValueError("claim card kind does not match its mechanical trigger")
        self.cards.append(card)

    def begin_verify_repair_cycle(self) -> int:
        if self.verify_repair_cycles >= self.max_cycles:
            raise RepairCycleLimitError(f"CHALLENGER is bounded to {self.max_cycles} verify/repair cycles")
        self.verify_repair_cycles += 1
        return self.verify_repair_cycles

    def record_check_result(self, result: CheckResult) -> None:
        if result.cycle > self.verify_repair_cycles:
            raise ValueError("check result cycle has not been opened")
        self.check_results.append(result)

    def record_questionnaire(self, round_: QuestionnaireRound) -> None:
        if round_.cycle != self.verify_repair_cycles:
            raise ValueError("questionnaire result must belong to the current task-local cycle")
        self.questionnaire_receipts.append({
            "cycle": round_.cycle,
            "schema": QUESTIONNAIRE_SCHEMA,
            "question_ids": sorted(round_.answers),
            "answers": {
                key: {
                    "choice": answer.choice,
                    "confidence": answer.confidence,
                    "evidence_refs": list(answer.evidence_refs),
                }
                for key, answer in round_.answers.items()
            },
        })

    def record_action(self, kind: ActionKind, *, check_id: str = "", detail: str = "") -> None:
        self.action_receipts.append({
            "cycle": self.verify_repair_cycles,
            "action": kind.value,
            "check_id": check_id,
            "detail": detail,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": LEDGER_SCHEMA,
            "identity": asdict(self.identity),
            "thresholds": {
                "no_change_actions": self.no_change_threshold,
                "material_action_interval": self.material_action_interval,
                "max_cycles": self.max_cycles,
            },
            "accepted_action_count": self.accepted_action_count,
            "material_action_count": self.material_action_count,
            "no_change_action_count": self.no_change_action_count,
            "last_state_fingerprint": self.last_state_fingerprint,
            "first_production_write_seen": self.first_production_write_seen,
            "seen_signatures": sorted(self.seen_signatures),
            "fired_repeat_signatures": sorted(self.fired_repeat_signatures),
            "fired_failure_action_ids": sorted(self.fired_failure_action_ids),
            "trigger_events": [
                {**asdict(item), "kind": item.kind.value} for item in self.trigger_events
            ],
            "cards": [_card_to_dict(item) for item in self.cards],
            "check_results": [asdict(item) for item in self.check_results],
            "questionnaire_receipts": self.questionnaire_receipts,
            "action_receipts": self.action_receipts,
            "verify_repair_cycles": self.verify_repair_cycles,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, expected_identity: LedgerIdentity) -> "TaskLocalClaimLedger":
        if value.get("schema") != LEDGER_SCHEMA:
            raise ValueError("unsupported CHALLENGER ledger schema")
        raw_identity = value.get("identity")
        if not isinstance(raw_identity, Mapping):
            raise ValueError("CHALLENGER ledger identity is missing")
        stored_identity = LedgerIdentity(
            run_id=str(raw_identity.get("run_id") or ""),
            task_prompt_sha256=str(raw_identity.get("task_prompt_sha256") or ""),
        )
        if stored_identity != expected_identity:
            raise ValueError("refusing to load a CHALLENGER ledger for a different task/run")
        thresholds = value.get("thresholds")
        if not isinstance(thresholds, Mapping):
            raise ValueError("CHALLENGER trigger thresholds are missing")
        ledger = cls(
            stored_identity,
            no_change_actions=int(thresholds.get("no_change_actions") or 0),
            material_action_interval=int(thresholds.get("material_action_interval") or 0),
            max_cycles=int(thresholds.get("max_cycles") or MAX_VERIFY_REPAIR_CYCLES),
        )
        ledger.accepted_action_count = int(value.get("accepted_action_count") or 0)
        ledger.material_action_count = int(value.get("material_action_count") or 0)
        ledger.no_change_action_count = int(value.get("no_change_action_count") or 0)
        ledger.last_state_fingerprint = str(value.get("last_state_fingerprint") or "")
        ledger.first_production_write_seen = bool(value.get("first_production_write_seen"))
        ledger.seen_signatures = {str(item) for item in value.get("seen_signatures", ())}
        ledger.fired_repeat_signatures = {str(item) for item in value.get("fired_repeat_signatures", ())}
        ledger.fired_failure_action_ids = {str(item) for item in value.get("fired_failure_action_ids", ())}
        for row in value.get("trigger_events", ()):
            ledger.trigger_events.append(TriggerEvent(
                str(row["trigger_id"]), TriggerKind(str(row["kind"])),
                int(row["action_ordinal"]), tuple(str(item) for item in row.get("reasons", ())),
            ))
        ledger.cards = [_card_from_dict(row) for row in value.get("cards", ())]
        ledger.check_results = [CheckResult(**row) for row in value.get("check_results", ())]
        ledger.questionnaire_receipts = [dict(row) for row in value.get("questionnaire_receipts", ())]
        ledger.action_receipts = [dict(row) for row in value.get("action_receipts", ())]
        ledger.verify_repair_cycles = int(value.get("verify_repair_cycles") or 0)
        if not 0 <= ledger.verify_repair_cycles <= ledger.max_cycles:
            raise ValueError("CHALLENGER cycle count is outside the declared bound")
        return ledger


class TaskLocalLedgerStore:
    """Persist one ledger under a caller-provided private, run-local state root."""

    def __init__(self, task_local_state_root: Path) -> None:
        self.root = Path(task_local_state_root)
        self.path = self.root / "challenger_claim_ledger.json"

    def load_or_create(self, identity: LedgerIdentity) -> TaskLocalClaimLedger:
        if not self.path.exists():
            return TaskLocalClaimLedger(identity)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("existing CHALLENGER ledger is unreadable; refusing to reset it") from exc
        if not isinstance(payload, Mapping):
            raise ValueError("existing CHALLENGER ledger must be an object")
        return TaskLocalClaimLedger.from_dict(payload, expected_identity=identity)

    def save(self, ledger: TaskLocalClaimLedger) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                existing = json.loads(self.path.read_text(encoding="utf-8"))
                raw_identity = existing.get("identity") if isinstance(existing, Mapping) else None
                if not isinstance(raw_identity, Mapping):
                    raise ValueError("existing CHALLENGER ledger has no valid identity")
                existing_identity = LedgerIdentity(
                    str(raw_identity.get("run_id") or ""),
                    str(raw_identity.get("task_prompt_sha256") or ""),
                )
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise ValueError("existing CHALLENGER ledger cannot be identity-checked; refusing to overwrite") from exc
            if existing_identity != ledger.identity:
                raise ValueError("refusing to overwrite a CHALLENGER ledger for a different task/run")
        data = json.dumps(ledger.to_dict(), sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root, prefix=".challenger-ledger-", delete=False
            ) as stream:
                temp_path = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


def _card_to_dict(card: ClaimCard) -> dict[str, Any]:
    if isinstance(card, DiagnosisCard):
        return {
            "kind": card.kind.value, "card_id": card.card_id, "trigger_id": card.trigger_id,
            "symptom": card.symptom,
            "hypotheses": [
                {
                    "hypothesis_id": item.hypothesis_id, "statement": item.statement,
                    "disposition": item.disposition, "discriminating_check": _check_to_dict(item.discriminating_check),
                } for item in card.hypotheses
            ],
        }
    if isinstance(card, ProgressClaimCard):
        return {
            "kind": card.kind.value, "card_id": card.card_id, "trigger_id": card.trigger_id,
            "criterion_id": card.criterion_id, "claim": card.claim,
            "evidence_refs": list(card.evidence_refs), "active_hypothesis_id": card.active_hypothesis_id,
        }
    return {
        "kind": card.kind.value, "card_id": card.card_id, "trigger_id": card.trigger_id,
        "claims": [asdict(item) for item in card.claims],
    }


def _card_from_dict(row: Mapping[str, Any]) -> ClaimCard:
    kind = CardKind(str(row["kind"]))
    if kind == CardKind.DIAGNOSIS:
        hypotheses = tuple(Hypothesis(
            str(item["hypothesis_id"]), str(item["statement"]), str(item["disposition"]),
            _check_from_dict(item["discriminating_check"]),
        ) for item in row["hypotheses"])
        return DiagnosisCard(str(row["card_id"]), str(row["trigger_id"]), str(row["symptom"]), hypotheses)
    if kind == CardKind.PROGRESS:
        return ProgressClaimCard(
            str(row["card_id"]), str(row["trigger_id"]), str(row["criterion_id"]),
            str(row["claim"]), tuple(row.get("evidence_refs", ())), str(row.get("active_hypothesis_id") or ""),
        )
    claims = tuple(CriterionClaim(
        str(item["criterion_id"]), tuple(item["evidence_refs"]), tuple(item["check_ids"]),
        str(item.get("source") or "glm_card")
    ) for item in row["claims"])
    return CompletionCard(str(row["card_id"]), str(row["trigger_id"]), claims)


def _check_to_dict(check: RunnableCheck) -> dict[str, str]:
    return {
        "check_id": check.check_id, "criterion_id": check.criterion_id,
        "description": check.description, "command": check.command,
        "origin": check.origin.value, "kind": check.kind.value,
    }


def _check_from_dict(row: Mapping[str, Any]) -> RunnableCheck:
    return RunnableCheck(
        str(row["check_id"]), str(row["criterion_id"]), str(row["description"]),
        str(row["command"]), CheckOrigin(str(row["origin"])), CheckKind(str(row["kind"])),
    )
