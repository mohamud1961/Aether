"""Shared types and bounds for the provider-free CHALLENGER claim ledger."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping, Protocol


LEDGER_SCHEMA = "aether.challenger.task_local_claim_ledger.v1"
QUESTIONNAIRE_SCHEMA = "aether.challenger.typed_questionnaire.v1"
MAX_VERIFY_REPAIR_CYCLES = 3
DEFAULT_NO_CHANGE_ACTIONS = 3
DEFAULT_MATERIAL_ACTION_INTERVAL = 5
DIAGNOSIS_MIN_PROBABILITY = 0.5  # separating-check / top-hypothesis floor for running a T1 check
DEFAULT_CONFIDENCE_THRESHOLD = 0.90  # provisional until the authorized replay set is calibrated
MAX_CHECK_MENU = 8
MAX_CHECK_COMMAND_CHARS = 2000
MAX_CHECK_OUTPUT_CHARS = 4096
MAX_EVIDENCE_VIEWS = 64
MAX_EVIDENCE_VIEW_CHARS = 8192
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class TriggerKind(str, Enum):
    FIRST_PRODUCTION_WRITE = "first_production_write"
    STUCK_OR_CONTRADICTED = "stuck_or_contradicted"
    PROGRESS_MILESTONE = "progress_milestone"
    FINISH_INTENT = "finish_intent"


class CardKind(str, Enum):
    DIAGNOSIS = "diagnosis"
    PROGRESS = "progress"
    COMPLETION = "completion"


class CheckOrigin(str, Enum):
    GLM = "glm"
    TASK = "task"


class CheckKind(str, Enum):
    READ_ONLY_INSPECTION = "read_only_inspection"
    TASK_PROVIDED_TEST = "task_provided_test"


class QuestionDimension(str, Enum):
    PROGRESS = "progress"
    ACTIVE_HYPOTHESIS = "active_hypothesis"
    COMPLETENESS = "completeness"
    CHECK_EXERCISES_REQUIREMENT = "check_exercises_requirement"
    CHECK_INDEPENDENCE = "check_independence"
    CHECK_RESULT_IMPLIES_REQUIREMENT = "check_result_implies_requirement"
    HYPOTHESIS_RANK = "hypothesis_rank"
    SEPARATING_CHECK = "separating_check"
    FOLLOWUP_CHECK = "followup_check"
    FOLLOWUP_RESULT = "followup_result"
    FAILURE_MODE = "failure_mode"
    CRITERION_STATUS = "criterion_status"


class ActionKind(str, Enum):
    HOLD_FINISH = "hold_finish"
    RUN_CHECK = "run_check"
    REQUEST_GLM_CHECK = "request_glm_check"
    ASK_JUDGE_FOLLOWUP = "ask_judge_followup"
    REFRESH_DIAGNOSIS = "refresh_diagnosis"
    ADMIT_FINISH = "admit_finish"
    ADVISORY_ONLY = "advisory_only"


@dataclass(frozen=True)
class LedgerIdentity:
    """Opaque per-run identity; the task text itself is never stored here."""

    run_id: str
    task_prompt_sha256: str

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id must be non-empty")
        if not _SHA256_RE.fullmatch(self.task_prompt_sha256):
            raise ValueError("task_prompt_sha256 must be lowercase SHA-256 hex")


@dataclass(frozen=True)
class FileWrite:
    path: str
    is_scratch: bool

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise ValueError("write path must be non-empty")


@dataclass(frozen=True)
class ActionObservation:
    action_id: str
    accepted: bool
    state_fingerprint: str
    material: bool = False
    writes: tuple[FileWrite, ...] = ()
    repeat_signature: str = ""
    unexpected_failure: bool = False
    contradicted_claim_ids: tuple[str, ...] = ()
    finish_intent: bool = False

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id must be non-empty")
        if not self.state_fingerprint.strip():
            raise ValueError("state_fingerprint must be non-empty")


@dataclass(frozen=True)
class TriggerEvent:
    trigger_id: str
    kind: TriggerKind
    action_ordinal: int
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    text: str

    def __post_init__(self) -> None:
        if not self.criterion_id.strip() or not self.text.strip():
            raise ValueError("criterion id and text must be non-empty")


@dataclass(frozen=True)
class RunnableCheck:
    check_id: str
    criterion_id: str
    description: str
    command: str
    origin: CheckOrigin
    kind: CheckKind

    def __post_init__(self) -> None:
        if not all((self.check_id.strip(), self.criterion_id.strip(), self.description.strip(), self.command.strip())):
            raise ValueError("check id, criterion, description, and command must be non-empty")
        if len(self.command) > MAX_CHECK_COMMAND_CHARS:
            raise ValueError("check command exceeds the bounded command length")
        if not isinstance(self.origin, CheckOrigin) or not isinstance(self.kind, CheckKind):
            raise ValueError("check origin and kind must use the declared enums")
        if self.kind == CheckKind.TASK_PROVIDED_TEST and self.origin != CheckOrigin.TASK:
            raise ValueError("task-provided tests must be marked with task origin")


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    disposition: str  # considered | dismissed
    discriminating_check: RunnableCheck

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip() or not self.statement.strip():
            raise ValueError("hypothesis id and statement must be non-empty")
        if self.disposition not in {"considered", "dismissed"}:
            raise ValueError("hypothesis disposition must be considered or dismissed")
        if self.discriminating_check.origin != CheckOrigin.GLM:
            raise ValueError("diagnosis cards must contain GLM-authored discriminating checks")


@dataclass(frozen=True)
class DiagnosisCard:
    card_id: str
    trigger_id: str
    symptom: str
    hypotheses: tuple[Hypothesis, ...]
    kind: CardKind = field(default=CardKind.DIAGNOSIS, init=False)

    def __post_init__(self) -> None:
        if not self.card_id.strip() or not self.trigger_id.strip() or not self.symptom.strip():
            raise ValueError("diagnosis card id, trigger, and symptom must be non-empty")
        if not 2 <= len(self.hypotheses) <= 4:
            raise ValueError("diagnosis cards require 2 to 4 hypotheses")
        if len({item.hypothesis_id for item in self.hypotheses}) != len(self.hypotheses):
            raise ValueError("hypothesis ids must be unique within a card")


@dataclass(frozen=True)
class ProgressClaimCard:
    card_id: str
    trigger_id: str
    criterion_id: str
    claim: str
    evidence_refs: tuple[str, ...]
    active_hypothesis_id: str = ""
    kind: CardKind = field(default=CardKind.PROGRESS, init=False)

    def __post_init__(self) -> None:
        if not all((self.card_id.strip(), self.trigger_id.strip(), self.criterion_id.strip(), self.claim.strip())):
            raise ValueError("progress card id, trigger, criterion, and claim must be non-empty")
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence refs must be non-empty strings")


@dataclass(frozen=True)
class CriterionClaim:
    criterion_id: str
    evidence_refs: tuple[str, ...]
    check_ids: tuple[str, ...]
    source: str = "glm_card"  # glm_card | task_text

    def __post_init__(self) -> None:
        if not self.criterion_id.strip():
            raise ValueError("criterion_id must be non-empty")
        if not self.evidence_refs or any(not item.strip() for item in self.evidence_refs):
            raise ValueError("each completion claim needs evidence references")
        if not self.check_ids or any(not item.strip() for item in self.check_ids):
            raise ValueError("each completion claim needs at least one check")


@dataclass(frozen=True)
class CompletionCard:
    card_id: str
    trigger_id: str
    claims: tuple[CriterionClaim, ...]
    kind: CardKind = field(default=CardKind.COMPLETION, init=False)

    def __post_init__(self) -> None:
        if not self.card_id.strip() or not self.trigger_id.strip():
            raise ValueError("completion card id and trigger must be non-empty")
        if not self.claims:
            raise ValueError("completion card must claim at least one criterion")
        ids = [claim.criterion_id for claim in self.claims]
        if len(set(ids)) != len(ids):
            raise ValueError("completion criterion ids must be unique")


ClaimCard = DiagnosisCard | ProgressClaimCard | CompletionCard


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    cycle: int
    ran: bool
    exit_code: int | None
    evidence_ref: str
    result_sha256: str
    output_excerpt: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or self.cycle < 1:
            raise ValueError("check result requires a check id and valid cycle")
        if self.ran and self.exit_code is None:
            raise ValueError("a run check result must include its exit code")
        if not self.evidence_ref.strip() or not _SHA256_RE.fullmatch(self.result_sha256):
            raise ValueError("check result requires an evidence ref and SHA-256")
        if len(self.output_excerpt) > MAX_CHECK_OUTPUT_CHARS:
            raise ValueError("check output excerpt exceeds the bounded evidence length")


@dataclass(frozen=True)
class MechanicalFacts:
    """Aether-owned facts kept outside the JUDGE question set."""

    check_results: tuple[CheckResult, ...] = ()
    changed_files: tuple[str, ...] = ()
    previously_passing_checks: Mapping[str, bool] = field(default_factory=dict)
    previous_checks_snapshot_complete: bool = False

    @property
    def previous_checks_pass(self) -> bool:
        return all(self.previously_passing_checks.values())

    def result_for(self, check_id: str) -> CheckResult | None:
        matches = [row for row in self.check_results if row.check_id == check_id and row.ran]
        return matches[-1] if matches else None


@dataclass(frozen=True)
class QuestionSpec:
    question_id: str
    dimension: QuestionDimension
    relation: str
    choices: tuple[str, ...]
    criterion_id: str = ""
    check_id: str = ""
    evidence_refs: tuple[str, ...] = ()
    context_text: str = ""
    choice_details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.question_id.strip() or not self.relation.strip():
            raise ValueError("question id and relation must be non-empty")
        if not self.choices or len(set(self.choices)) != len(self.choices):
            raise ValueError("question choices must be non-empty and unique")
        if any(not item.strip() for item in self.choices):
            raise ValueError("question choices must be non-empty strings")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "relation": self.relation,
            "choices": list(self.choices),
            "criterion_id": self.criterion_id,
            "check_id": self.check_id,
            "evidence_refs": list(self.evidence_refs),
            "context_text": self.context_text,
            "choice_details": dict(self.choice_details),
        }


@dataclass(frozen=True)
class QuestionAnswer:
    question_id: str
    choice: str
    confidence: float
    evidence_refs: tuple[str, ...] = ()
    probabilities: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestionnaireRound:
    cycle: int
    questions: tuple[QuestionSpec, ...]
    answers: Mapping[str, QuestionAnswer]


class QuestionEvaluator(Protocol):
    def __call__(
        self,
        state: Mapping[str, Any],
        questions: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Mapping[str, Any]]: ...


class QuestionnaireSchemaError(ValueError):
    pass


class RepairCycleLimitError(RuntimeError):
    pass
