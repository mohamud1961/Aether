"""Provider-free CHALLENGER claim ledger and typed JUDGE verify/repair policy.

This module remains the stable import surface. Implementations are divided
among the focused modules while existing callers keep importing from here.
"""
from __future__ import annotations

from .challenger_claim_types import (
    LEDGER_SCHEMA,
    QUESTIONNAIRE_SCHEMA,
    MAX_VERIFY_REPAIR_CYCLES,
    DEFAULT_NO_CHANGE_ACTIONS,
    DEFAULT_MATERIAL_ACTION_INTERVAL,
    DEFAULT_CONFIDENCE_THRESHOLD,
    MAX_CHECK_MENU,
    MAX_CHECK_COMMAND_CHARS,
    MAX_CHECK_OUTPUT_CHARS,
    MAX_EVIDENCE_VIEWS,
    MAX_EVIDENCE_VIEW_CHARS,
    TriggerKind,
    CardKind,
    CheckOrigin,
    CheckKind,
    QuestionDimension,
    ActionKind,
    LedgerIdentity,
    FileWrite,
    ActionObservation,
    TriggerEvent,
    Criterion,
    RunnableCheck,
    Hypothesis,
    DiagnosisCard,
    ProgressClaimCard,
    CriterionClaim,
    CompletionCard,
    ClaimCard,
    CheckResult,
    MechanicalFacts,
    QuestionSpec,
    QuestionAnswer,
    QuestionnaireRound,
    QuestionEvaluator,
    QuestionnaireSchemaError,
    RepairCycleLimitError,
    _SHA256_RE,
)
from .challenger_claim_ledger_state import (
    TaskLocalClaimLedger,
    TaskLocalLedgerStore,
    _card_to_dict,
    _card_from_dict,
    _check_to_dict,
    _check_from_dict,
)
from .challenger_claim_questionnaire import (
    QuestionnaireContext,
    build_questions,
    build_followup_check_questions,
    build_followup_result_questions,
    QuestionnaireRunner,
    _parse_answers,
    _known_refs,
    _require_criterion,
)
from .challenger_claim_policy import (
    ActionDecision,
    ActionContext,
    CheckRunner,
    choose_action,
    _choose_action_impl,
    render_feedback,
    execute_action,
    _replacement_check,
    _answer_refs,
    _ACTION_POLICY_SEAL,
)
