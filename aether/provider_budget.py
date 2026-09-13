"""Fail-closed monetary admission for budget-constrained provider runs.

The normal production profile remains unchanged. A launch that opts into a
budget contract binds an exact JSON contract by path+SHA256. Every actual
Responses *create* invocation reserves its conservative worst-case GBP cost
before network dispatch. The reservation is intentionally not refunded: a
transport failure may still have reached the provider, and missing usage is
never treated as zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import os
from pathlib import Path
import threading
from typing import Any, Mapping


BUDGET_SCHEMA_V1 = "aether.provider_budget.v1"
BUDGET_SCHEMA_V2 = "aether.provider_budget.v2"
# Backward-compatible public alias used by existing v1 callers/tests.
BUDGET_SCHEMA = BUDGET_SCHEMA_V1
BUDGET_PATH_ENV = "AETHER_PROVIDER_BUDGET_PATH"
BUDGET_SHA256_ENV = "AETHER_PROVIDER_BUDGET_SHA256"
BUDGET_JOURNAL_ENV = "AETHER_PROVIDER_BUDGET_JOURNAL"
_ROLES = ("solver", "verifier", "vision")
_MILLION = Decimal("1000000")
# Canonical model ID for the separately opted-in GPT-6-Luna research profile.
# It is admitted only by the bounded v1 contract path below; the production
# GPT-5.6-Luna profile and its serialized contract hashes remain unchanged.
GPT6_FRONTIER_BUDGET_MODEL_ID = "gpt-6-luna"
# Operator-supplied OpenAI GPT-5.6 Frontier list pricing, sealed into this source candidate.
# We conservatively reserve the USD list-price number as the same numeric GBP
# amount (1 USD -> 1 GBP) so no optimistic FX conversion is required. These
# rates are reservation ceilings when used by a GPT-6-Luna contract; they are
# not represented as GPT-6-Luna's published prices.
FRONTIER_SHORT_INPUT_GBP_PER_MILLION_FLOOR = Decimal("0.20")
FRONTIER_SHORT_OUTPUT_GBP_PER_MILLION_FLOOR = Decimal("1.20")
FRONTIER_LONG_CONTEXT_THRESHOLD_TOKENS = 272_000
# Official provider hard limits for GPT-5.6 Frontier. V2 transparent budget
# contracts may reserve against these natural limits instead of imposing a
# tighter harness-authored runtime cap.
FRONTIER_CONTEXT_WINDOW_TOKENS = 1_050_000
FRONTIER_MAX_OUTPUT_TOKENS = 128_000
FRONTIER_LONG_INPUT_MULTIPLIER = Decimal("2")
FRONTIER_LONG_OUTPUT_MULTIPLIER = Decimal("1.5")
FRONTIER_CACHE_WRITE_INPUT_MULTIPLIER = Decimal("1.25")
FRONTIER_PRICING_REFERENCE = "openai-gpt-5.6-luna-list-2026-09-10-usd-as-gbp-conservative"


class ProviderBudgetError(RuntimeError):
    """Budget contract is invalid or a provider dispatch is not affordable."""


@dataclass(frozen=True)
class RoleBudget:
    max_provider_creates: int
    max_input_tokens: int
    max_output_tokens: int
    input_gbp_per_million: Decimal
    output_gbp_per_million: Decimal

    def worst_case_gbp(self) -> Decimal:
        return reservation_gbp(
            self, input_tokens=self.max_input_tokens, output_tokens=self.max_output_tokens,
        )


def reservation_gbp(row: "RoleBudget", *, input_tokens: int, output_tokens: int) -> Decimal:
    long_context = int(input_tokens) > FRONTIER_LONG_CONTEXT_THRESHOLD_TOKENS
    # Cache-write state is not knowable before dispatch. Reserve every input
    # token at the documented 1.25x cache-write rate, then apply the long-context
    # multiplier when the conservative input upper bound crosses 272K.
    input_rate = (
        row.input_gbp_per_million
        * FRONTIER_CACHE_WRITE_INPUT_MULTIPLIER
        * (FRONTIER_LONG_INPUT_MULTIPLIER if long_context else Decimal("1"))
    )
    output_rate = row.output_gbp_per_million * (FRONTIER_LONG_OUTPUT_MULTIPLIER if long_context else Decimal("1"))
    return (Decimal(int(input_tokens)) * input_rate + Decimal(int(output_tokens)) * output_rate) / _MILLION


@dataclass(frozen=True)
class ProviderBudgetContract:
    schema_version: str
    budget_id: str
    model_id: str
    currency: str
    budget_constrained: bool
    total_cap_gbp: Decimal
    provider_max_retries: int
    provider_sdk_max_retries: int
    solver_turn_budget: int | None
    runtime_max_output_tokens: Mapping[str, int | None]
    agent_timeout_sec: float
    vm_incremental_cap_gbp: Decimal
    roles: Mapping[str, RoleBudget]

    @property
    def max_total_provider_creates(self) -> int:
        return sum(row.max_provider_creates for row in self.roles.values())

    @property
    def worst_case_total_gbp(self) -> Decimal:
        """Return the product of every create ceiling and per-create reservation ceiling.

        V1 requires this theoretical product to fit within ``total_cap_gbp``.
        V2 deliberately does not: every actual create is reserved atomically
        against ``total_cap_gbp`` before dispatch, so the monetary cap remains
        hard without forcing runtime cognitive ceilings to be artificially low.
        """
        return sum(
            (Decimal(row.max_provider_creates) * row.worst_case_gbp() for row in self.roles.values()),
            Decimal("0"),
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "budget_id": self.budget_id,
            "model_id": self.model_id,
            "currency": self.currency,
            "budget_constrained": self.budget_constrained,
            "total_cap_gbp": _decimal_text(self.total_cap_gbp),
            "provider_max_retries": self.provider_max_retries,
            "provider_sdk_max_retries": self.provider_sdk_max_retries,
            "agent_timeout_sec": self.agent_timeout_sec,
            "vm_incremental_cap_gbp": _decimal_text(self.vm_incremental_cap_gbp),
            "roles": {
                role: {
                    "max_provider_creates": row.max_provider_creates,
                    "max_input_tokens": row.max_input_tokens,
                    "max_output_tokens": row.max_output_tokens,
                    "input_gbp_per_million": _decimal_text(row.input_gbp_per_million),
                    "output_gbp_per_million": _decimal_text(row.output_gbp_per_million),
                }
                for role, row in sorted(self.roles.items())
            },
        }
        if self.schema_version == BUDGET_SCHEMA_V1:
            # Preserve the exact legacy v1 canonical JSON and therefore every
            # already-sealed H1/H2 contract hash.
            payload["solver_turn_budget"] = self.solver_turn_budget
        elif self.schema_version == BUDGET_SCHEMA_V2:
            payload["runtime_limits"] = {
                "solver_turn_budget": self.solver_turn_budget,
                "solver_max_output_tokens": self.runtime_max_output_tokens.get("solver"),
                "verifier_max_output_tokens": self.runtime_max_output_tokens.get("verifier"),
                "vision_max_output_tokens": self.runtime_max_output_tokens.get("vision"),
            }
        else:  # pragma: no cover - construction is parser-owned
            raise ProviderBudgetError(f"unsupported budget schema_version: {self.schema_version}")
        return payload

    def sha256(self) -> str:
        return contract_sha256(self.as_dict())


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _decimal(value: Any, *, field: str, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProviderBudgetError(f"{field} must be a finite decimal") from exc
    if not result.is_finite():
        raise ProviderBudgetError(f"{field} must be finite")
    if positive and result <= 0:
        raise ProviderBudgetError(f"{field} must be > 0")
    if not positive and result < 0:
        raise ProviderBudgetError(f"{field} must be >= 0")
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], *, field: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise ProviderBudgetError(f"{field} keys invalid: missing={missing}, unknown={unknown}")


def _optional_positive_int(value: Any, *, field: str) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderBudgetError(f"{field} must be null or a positive integer") from exc
    if result <= 0:
        raise ProviderBudgetError(f"{field} must be null or > 0")
    return result


def parse_budget_contract(value: Mapping[str, Any]) -> ProviderBudgetContract:
    if not isinstance(value, Mapping):
        raise ProviderBudgetError("budget contract must be an object")
    schema = str(value.get("schema_version") or "").strip()
    common_keys = {
        "schema_version", "budget_id", "model_id", "currency", "budget_constrained",
        "total_cap_gbp", "provider_max_retries", "provider_sdk_max_retries",
        "agent_timeout_sec", "vm_incremental_cap_gbp", "roles",
    }
    if schema == BUDGET_SCHEMA_V1:
        _exact_keys(value, common_keys | {"solver_turn_budget"}, field="budget contract")
    elif schema == BUDGET_SCHEMA_V2:
        _exact_keys(value, common_keys | {"runtime_limits"}, field="budget contract")
    else:
        raise ProviderBudgetError("unsupported budget schema_version")

    budget_id = str(value.get("budget_id") or "").strip()
    if not budget_id or len(budget_id) > 160:
        raise ProviderBudgetError("budget_id must be non-empty and <= 160 characters")
    model_id = str(value.get("model_id") or "").strip()
    from .model_profile import GLM_RESEARCH_PROFILE, PRODUCTION_PROFILE
    allowed_models = {PRODUCTION_PROFILE.model_id}
    if schema == BUDGET_SCHEMA_V2:
        allowed_models.add(GLM_RESEARCH_PROFILE.model_id)
    else:
        allowed_models.add(GPT6_FRONTIER_BUDGET_MODEL_ID)
    if model_id not in allowed_models:
        raise ProviderBudgetError("budget contract model_id has no admitted budget profile")
    if value.get("currency") != "GBP":
        raise ProviderBudgetError("budget currency must be GBP")
    if value.get("budget_constrained") is not True:
        raise ProviderBudgetError("budget_constrained must be true")
    try:
        provider_max_retries = int(value.get("provider_max_retries"))
        sdk_max_retries = int(value.get("provider_sdk_max_retries"))
        agent_timeout_sec = float(value.get("agent_timeout_sec"))
    except (TypeError, ValueError) as exc:
        raise ProviderBudgetError("retry/time limits must be numeric") from exc
    if schema == BUDGET_SCHEMA_V1:
        if provider_max_retries != 0 or sdk_max_retries != 0:
            raise ProviderBudgetError("budget-constrained provider and SDK retries must both be 0")
        solver_turn_budget = _optional_positive_int(
            value.get("solver_turn_budget"), field="solver_turn_budget"
        )
        if solver_turn_budget is None:
            raise ProviderBudgetError("solver_turn_budget must be > 0")
        runtime_limits_raw: Mapping[str, Any] | None = None
    else:
        # V2 allows the already-qualified production retry policy while the
        # guard reserves every retry create before transport. SDK retries stay
        # zero because they are not independently lifecycle-attributed.
        if provider_max_retries not in {0, 1} or sdk_max_retries != 0:
            raise ProviderBudgetError(
                "v2 provider_max_retries must be 0 or 1 and provider_sdk_max_retries must be 0"
            )
        runtime_value = value.get("runtime_limits")
        if not isinstance(runtime_value, Mapping):
            raise ProviderBudgetError("runtime_limits must be an object")
        _exact_keys(runtime_value, {
            "solver_turn_budget", "solver_max_output_tokens",
            "verifier_max_output_tokens", "vision_max_output_tokens",
        }, field="runtime_limits")
        runtime_limits_raw = runtime_value
        solver_turn_budget = _optional_positive_int(
            runtime_value.get("solver_turn_budget"), field="runtime_limits.solver_turn_budget"
        )
    if not (agent_timeout_sec > 0 and agent_timeout_sec < float("inf")):
        raise ProviderBudgetError("agent_timeout_sec must be finite and > 0")

    roles_value = value.get("roles")
    if not isinstance(roles_value, Mapping):
        raise ProviderBudgetError("roles must be an object")
    _exact_keys(roles_value, set(_ROLES), field="roles")
    roles: dict[str, RoleBudget] = {}
    role_keys = {
        "max_provider_creates", "max_input_tokens", "max_output_tokens",
        "input_gbp_per_million", "output_gbp_per_million",
    }
    for role in _ROLES:
        raw = roles_value.get(role)
        if not isinstance(raw, Mapping):
            raise ProviderBudgetError(f"roles.{role} must be an object")
        _exact_keys(raw, role_keys, field=f"roles.{role}")
        try:
            creates = int(raw.get("max_provider_creates"))
            input_tokens = int(raw.get("max_input_tokens"))
            output_tokens = int(raw.get("max_output_tokens"))
        except (TypeError, ValueError) as exc:
            raise ProviderBudgetError(f"roles.{role} integer ceilings are invalid") from exc
        if creates < 0:
            raise ProviderBudgetError(f"roles.{role}.max_provider_creates must be >= 0")
        if input_tokens <= 0 or output_tokens <= 0:
            raise ProviderBudgetError(f"roles.{role} token ceilings must be > 0")
        input_rate = _decimal(
            raw.get("input_gbp_per_million"), field=f"roles.{role}.input_gbp_per_million"
        )
        output_rate = _decimal(
            raw.get("output_gbp_per_million"), field=f"roles.{role}.output_gbp_per_million"
        )
        if input_rate < FRONTIER_SHORT_INPUT_GBP_PER_MILLION_FLOOR:
            raise ProviderBudgetError(
                f"roles.{role}.input_gbp_per_million is below sealed Frontier pricing floor"
            )
        if output_rate < FRONTIER_SHORT_OUTPUT_GBP_PER_MILLION_FLOOR:
            raise ProviderBudgetError(
                f"roles.{role}.output_gbp_per_million is below sealed Frontier pricing floor"
            )
        roles[role] = RoleBudget(
            max_provider_creates=creates, max_input_tokens=input_tokens,
            max_output_tokens=output_tokens, input_gbp_per_million=input_rate,
            output_gbp_per_million=output_rate,
        )

    if schema == BUDGET_SCHEMA_V1:
        runtime_max_output_tokens: dict[str, int | None] = {
            role: roles[role].max_output_tokens for role in _ROLES
        }
    else:
        assert runtime_limits_raw is not None
        runtime_max_output_tokens = {}
        for role in _ROLES:
            field = f"{role}_max_output_tokens"
            runtime_cap = _optional_positive_int(
                runtime_limits_raw.get(field), field=f"runtime_limits.{field}"
            )
            if runtime_cap is not None and runtime_cap > roles[role].max_output_tokens:
                raise ProviderBudgetError(
                    f"runtime_limits.{field} exceeds roles.{role}.max_output_tokens reservation ceiling"
                )
            runtime_max_output_tokens[role] = runtime_cap
            if roles[role].max_provider_creates > 0 and runtime_cap is None:
                # A transparent runtime must reserve against the provider's
                # natural hard limits, not a tighter harness-authored ceiling.
                if roles[role].max_input_tokens < FRONTIER_CONTEXT_WINDOW_TOKENS:
                    raise ProviderBudgetError(
                        f"transparent v2 roles.{role}.max_input_tokens must cover Frontier context window"
                    )
                if roles[role].max_output_tokens < FRONTIER_MAX_OUTPUT_TOKENS:
                    raise ProviderBudgetError(
                        f"transparent v2 roles.{role}.max_output_tokens must cover Frontier natural output max"
                    )

    contract = ProviderBudgetContract(
        schema_version=schema, budget_id=budget_id, model_id=model_id, currency="GBP",
        budget_constrained=True,
        total_cap_gbp=_decimal(value.get("total_cap_gbp"), field="total_cap_gbp", positive=True),
        provider_max_retries=provider_max_retries,
        provider_sdk_max_retries=sdk_max_retries,
        solver_turn_budget=solver_turn_budget,
        runtime_max_output_tokens=runtime_max_output_tokens,
        agent_timeout_sec=agent_timeout_sec,
        vm_incremental_cap_gbp=_decimal(value.get("vm_incremental_cap_gbp"), field="vm_incremental_cap_gbp"),
        roles=roles,
    )
    if contract.max_total_provider_creates <= 0:
        raise ProviderBudgetError("budget contract must authorize at least one provider create")
    # V1 freezes a fully-enumerated worst-case envelope. V2 instead relies on
    # the same pre-dispatch atomic reservation guard to enforce total_cap_gbp,
    # allowing high/nonbinding provider-create ceilings and provider-natural
    # token limits without pretending all maxima can occur simultaneously.
    if schema == BUDGET_SCHEMA_V1 and contract.worst_case_total_gbp > contract.total_cap_gbp:
        raise ProviderBudgetError(
            "declared provider ceilings exceed total_cap_gbp: "
            f"worst_case={_decimal_text(contract.worst_case_total_gbp)} "
            f"cap={_decimal_text(contract.total_cap_gbp)}"
        )
    return contract

def canonical_contract_json(value: Mapping[str, Any]) -> str:
    contract = parse_budget_contract(value)
    return json.dumps(contract.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def contract_sha256(value: Mapping[str, Any]) -> str:
    return sha256(canonical_contract_json(value).encode("utf-8")).hexdigest()


def load_budget_contract(path: str | Path, *, expected_sha256: str | None = None) -> ProviderBudgetContract:
    raw_path = Path(path).expanduser().resolve(strict=True)
    try:
        value = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ProviderBudgetError(f"budget contract is not valid JSON: {exc}") from exc
    contract = parse_budget_contract(value)
    observed = contract.sha256()
    if expected_sha256 is not None and observed != str(expected_sha256).strip().lower():
        raise ProviderBudgetError("budget contract SHA256 does not match launch binding")
    return contract


def budget_contract_from_env() -> ProviderBudgetContract | None:
    raw_path = str(os.environ.get(BUDGET_PATH_ENV, "") or "").strip()
    raw_sha = str(os.environ.get(BUDGET_SHA256_ENV, "") or "").strip().lower()
    if not raw_path and not raw_sha:
        return None
    if not raw_path or not raw_sha:
        raise ProviderBudgetError("budget path and SHA256 must be provided together")
    if len(raw_sha) != 64 or any(ch not in "0123456789abcdef" for ch in raw_sha):
        raise ProviderBudgetError("budget SHA256 must be exact lowercase sha256")
    return load_budget_contract(raw_path, expected_sha256=raw_sha)


def serialized_request_token_upper_bound(request: Mapping[str, Any]) -> int:
    """Conservative token upper bound for the literal serialized request.

    UTF-8 bytes upper-bound ordinary text/BPE token count and also safely
    dominate inline base64 payload character counts. Provider-side prior
    response context must be added separately by the transport.
    """
    encoded = json.dumps(
        dict(request), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=str,
    ).encode("utf-8")
    return len(encoded)


def budget_journal_state(
    contract: ProviderBudgetContract, *, contract_sha: str, journal_path: str | Path,
) -> dict[str, Any]:
    """Validate and reconstruct one append-only reservation/settlement journal.

    V1 journals contain reservation rows only and retain their historical
    non-release semantics. V2 may additionally append authoritative success
    settlement rows. A settlement can only reduce a provisional reservation
    to a conservative charge derived from provider-reported usage that remains
    within the originally reserved token bounds. Missing/ambiguous usage never
    releases a reservation.
    """
    path = Path(journal_path).expanduser().resolve()
    counts = {role: 0 for role in _ROLES}
    total = 0
    reserved = Decimal("0")
    settlements = 0
    reservation_records: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return {
            "role_create_counts": counts, "aggregate_create_count": total,
            "reserved_gbp": reserved, "reservation_count": 0,
            "settlement_count": 0, "reservation_records": reservation_records,
        }
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProviderBudgetError(f"provider budget journal cannot be read: {exc}") from exc
    for line_ordinal, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProviderBudgetError(
                f"provider budget journal line {line_ordinal} is invalid JSON"
            ) from exc
        if not isinstance(event, Mapping):
            raise ProviderBudgetError(
                f"provider budget journal line {line_ordinal} must be an object"
            )
        schema = event.get("schema_version")
        if schema == "aether.provider_budget_settlement.v1":
            if contract.schema_version != BUDGET_SCHEMA_V2:
                raise ProviderBudgetError("provider budget settlement is only valid for v2 contracts")
            if str(event.get("budget_id") or "") != contract.budget_id:
                raise ProviderBudgetError("provider budget settlement budget_id mismatch")
            if str(event.get("model_id") or "") != contract.model_id:
                raise ProviderBudgetError("provider budget settlement model_id mismatch")
            if str(event.get("budget_contract_sha256") or "") != str(contract_sha):
                raise ProviderBudgetError("provider budget settlement contract SHA256 mismatch")
            if event.get("currency") != "GBP":
                raise ProviderBudgetError("provider budget settlement currency mismatch")
            try:
                aggregate_ordinal = int(event.get("aggregate_create_ordinal"))
                role_ordinal = int(event.get("role_create_ordinal"))
                input_tokens = int(event.get("provider_input_tokens"))
                output_tokens = int(event.get("provider_output_tokens"))
            except (TypeError, ValueError) as exc:
                raise ProviderBudgetError("provider budget settlement integer field is invalid") from exc
            record = reservation_records.get(aggregate_ordinal)
            if record is None:
                raise ProviderBudgetError("provider budget settlement references unknown reservation")
            role = str(event.get("role") or "")
            if role != record["role"] or role_ordinal != record["role_create_ordinal"]:
                raise ProviderBudgetError("provider budget settlement reservation identity mismatch")
            if record.get("settled"):
                raise ProviderBudgetError("provider budget reservation settled more than once")
            if input_tokens < 0 or output_tokens < 0:
                raise ProviderBudgetError("provider budget settlement usage must be non-negative")
            if input_tokens > int(record["input_token_upper_bound"]):
                raise ProviderBudgetError("provider budget settlement input usage exceeds reservation bound")
            if output_tokens > int(record["max_output_tokens"]):
                raise ProviderBudgetError("provider budget settlement output usage exceeds reservation bound")
            row = contract.roles[role]
            expected_settled = reservation_gbp(
                row, input_tokens=input_tokens, output_tokens=output_tokens,
            )
            original = Decimal(record["reserved_gbp"])
            if expected_settled > original:
                raise ProviderBudgetError("provider budget settlement exceeds original reservation")
            released = original - expected_settled
            try:
                recorded_settled = _decimal(event.get("settled_gbp"), field="settlement.settled_gbp")
                recorded_released = _decimal(event.get("released_provisional_gbp"), field="settlement.released_provisional_gbp")
                recorded_running = _decimal(event.get("running_reserved_gbp"), field="settlement.running_reserved_gbp")
            except ProviderBudgetError as exc:
                raise ProviderBudgetError(f"provider budget settlement arithmetic invalid: {exc}") from exc
            if recorded_settled != expected_settled or recorded_released != released:
                raise ProviderBudgetError("provider budget settlement arithmetic mismatch")
            next_reserved = reserved - released
            if next_reserved < 0 or recorded_running != next_reserved:
                raise ProviderBudgetError("provider budget settlement running total mismatch")
            if event.get("usage_source") != "provider_reported_terminal_success":
                raise ProviderBudgetError("provider budget settlement usage source invalid")
            if event.get("pricing_reference") != FRONTIER_PRICING_REFERENCE:
                raise ProviderBudgetError("provider budget settlement pricing reference mismatch")
            record["settled"] = True
            record["settled_gbp"] = expected_settled
            record["released_provisional_gbp"] = released
            reserved = next_reserved
            settlements += 1
            continue
        if schema != "aether.provider_budget_reservation.v1":
            raise ProviderBudgetError("provider budget journal schema mismatch")
        if str(event.get("budget_id") or "") != contract.budget_id:
            raise ProviderBudgetError("provider budget journal budget_id mismatch")
        if str(event.get("model_id") or "") != contract.model_id:
            raise ProviderBudgetError("provider budget journal model_id mismatch")
        if str(event.get("budget_contract_sha256") or "") != str(contract_sha):
            raise ProviderBudgetError("provider budget journal contract SHA256 mismatch")
        if event.get("currency") != "GBP":
            raise ProviderBudgetError("provider budget journal currency mismatch")
        role = str(event.get("role") or "")
        if role not in contract.roles:
            raise ProviderBudgetError(f"provider budget journal role is invalid: {role!r}")
        row = contract.roles[role]
        try:
            role_ordinal = int(event.get("role_create_ordinal"))
            aggregate_ordinal = int(event.get("aggregate_create_ordinal"))
            request_bytes = int(event.get("request_bytes"))
            input_upper = int(event.get("input_token_upper_bound"))
            requested_output = int(event.get("max_output_tokens"))
        except (TypeError, ValueError) as exc:
            raise ProviderBudgetError("provider budget journal integer field is invalid") from exc
        if role_ordinal != counts[role] + 1 or aggregate_ordinal != total + 1:
            raise ProviderBudgetError("provider budget journal ordinal sequence is invalid")
        if request_bytes <= 0 or input_upper < request_bytes:
            raise ProviderBudgetError("provider budget journal input bound is invalid")
        if input_upper > row.max_input_tokens:
            raise ProviderBudgetError("provider budget journal input bound exceeds contract")
        if requested_output <= 0 or requested_output > row.max_output_tokens:
            raise ProviderBudgetError("provider budget journal output bound exceeds contract")
        expected_reservation = reservation_gbp(
            row, input_tokens=input_upper, output_tokens=requested_output,
        )
        try:
            recorded_reservation = _decimal(event.get("reserved_gbp"), field="journal.reserved_gbp")
            recorded_running = _decimal(event.get("running_reserved_gbp"), field="journal.running_reserved_gbp")
        except ProviderBudgetError as exc:
            raise ProviderBudgetError(f"provider budget journal arithmetic invalid: {exc}") from exc
        if recorded_reservation != expected_reservation:
            raise ProviderBudgetError("provider budget journal reservation arithmetic mismatch")
        next_reserved = reserved + expected_reservation
        if recorded_running != next_reserved:
            raise ProviderBudgetError("provider budget journal running total mismatch")
        if recorded_running > contract.total_cap_gbp:
            raise ProviderBudgetError("provider budget journal exceeds contract cap")
        if bool(event.get("long_context_surcharge_applied")) != (
            input_upper > FRONTIER_LONG_CONTEXT_THRESHOLD_TOKENS
        ):
            raise ProviderBudgetError("provider budget journal long-context flag mismatch")
        if event.get("pricing_reference") != FRONTIER_PRICING_REFERENCE:
            raise ProviderBudgetError("provider budget journal pricing reference mismatch")
        if event.get("reservation_refundable") is not False:
            raise ProviderBudgetError("provider budget journal refundability invariant violated")
        counts[role] += 1
        total += 1
        reserved = next_reserved
        reservation_records[aggregate_ordinal] = {
            "role": role,
            "role_create_ordinal": role_ordinal,
            "aggregate_create_ordinal": aggregate_ordinal,
            "input_token_upper_bound": input_upper,
            "max_output_tokens": requested_output,
            "reserved_gbp": expected_reservation,
            "settled": False,
        }
    for role, count in counts.items():
        if count > contract.roles[role].max_provider_creates:
            raise ProviderBudgetError(f"provider budget journal exceeds {role} create ceiling")
    if total > contract.max_total_provider_creates:
        raise ProviderBudgetError("provider budget journal exceeds aggregate create ceiling")
    return {
        "role_create_counts": counts, "aggregate_create_count": total,
        "reserved_gbp": reserved, "reservation_count": total,
        "settlement_count": settlements, "reservation_records": reservation_records,
    }


class ProviderBudgetGuard:
    """One process-local, run-scoped conservative provider spend ledger."""

    def __init__(
        self,
        contract: ProviderBudgetContract,
        *,
        contract_sha: str,
        journal_path: str | Path | None = None,
    ) -> None:
        self.contract = contract
        self.contract_sha = str(contract_sha)
        self.journal_path = Path(journal_path).expanduser().resolve() if journal_path else None
        self._lock = threading.Lock()
        restored = (
            budget_journal_state(
                contract, contract_sha=self.contract_sha, journal_path=self.journal_path,
            )
            if self.journal_path is not None else {
                "role_create_counts": {role: 0 for role in _ROLES},
                "aggregate_create_count": 0, "reserved_gbp": Decimal("0"),
                "settlement_count": 0, "reservation_records": {},
            }
        )
        self._role_counts = dict(restored["role_create_counts"])
        self._total_count = int(restored["aggregate_create_count"])
        self._reserved_gbp = Decimal(restored["reserved_gbp"])
        self._settlement_count = int(restored.get("settlement_count") or 0)
        self._reservations = {
            int(k): dict(v) for k, v in dict(restored.get("reservation_records") or {}).items()
        }

    def _append_journal(self, event: Mapping[str, Any]) -> None:
        if self.journal_path is None:
            return
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(dict(event), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        fd = os.open(str(self.journal_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _request_bytes(request: Mapping[str, Any]) -> int:
        return serialized_request_token_upper_bound(request)

    def reserve(
        self, role: str, request: Mapping[str, Any], *, input_token_upper_bound: int | None = None,
    ) -> dict[str, Any]:
        role = str(role).strip()
        if role not in self.contract.roles:
            raise ProviderBudgetError(f"provider role is not budgeted: {role!r}")
        row = self.contract.roles[role]
        raw_requested_output = request.get("max_output_tokens")
        if raw_requested_output is None:
            if (
                self.contract.schema_version == BUDGET_SCHEMA_V2
                and self.contract.runtime_max_output_tokens.get(role) is None
            ):
                requested_output = row.max_output_tokens
                request_output = None
                output_bound_source = "provider_natural_max_reservation"
            else:
                raise ProviderBudgetError(
                    f"budgeted {role} request requires explicit max_output_tokens"
                )
        else:
            try:
                requested_output = int(raw_requested_output)
            except (TypeError, ValueError) as exc:
                raise ProviderBudgetError(
                    f"budgeted {role} max_output_tokens must be an integer"
                ) from exc
            request_output = requested_output
            output_bound_source = "request_max_output_tokens"
        if requested_output <= 0 or requested_output > row.max_output_tokens:
            raise ProviderBudgetError(
                f"budgeted {role} max_output_tokens exceeds contract: "
                f"requested={requested_output} cap={row.max_output_tokens}"
            )
        request_bytes = self._request_bytes(request)
        if input_token_upper_bound is None:
            input_upper = request_bytes
            input_bound_source = "serialized_request_bytes"
        else:
            try:
                input_upper = int(input_token_upper_bound)
            except (TypeError, ValueError) as exc:
                raise ProviderBudgetError("input_token_upper_bound must be an integer") from exc
            if input_upper < request_bytes:
                raise ProviderBudgetError(
                    "input_token_upper_bound may not be below serialized request bytes"
                )
            input_bound_source = "provider_continuity_plus_serialized_request_bytes"
        if input_upper <= 0 or input_upper > row.max_input_tokens:
            raise ProviderBudgetError(
                f"budgeted {role} input token upper bound exceeds contract: "
                f"upper={input_upper} cap={row.max_input_tokens}"
            )
        reservation = reservation_gbp(
            row, input_tokens=input_upper, output_tokens=requested_output,
        )
        with self._lock:
            if self._role_counts[role] >= row.max_provider_creates:
                raise ProviderBudgetError(
                    f"provider create ceiling exhausted for role {role}: {row.max_provider_creates}"
                )
            if self._total_count >= self.contract.max_total_provider_creates:
                raise ProviderBudgetError(
                    f"aggregate provider create ceiling exhausted: {self.contract.max_total_provider_creates}"
                )
            next_reserved = self._reserved_gbp + reservation
            if next_reserved > self.contract.total_cap_gbp:
                raise ProviderBudgetError(
                    "provider spend reservation would exceed GBP cap: "
                    f"next={_decimal_text(next_reserved)} cap={_decimal_text(self.contract.total_cap_gbp)}"
                )
            role_ordinal = self._role_counts[role] + 1
            aggregate_ordinal = self._total_count + 1
            event = {
                "schema_version": "aether.provider_budget_reservation.v1",
                "budget_id": self.contract.budget_id,
                "model_id": self.contract.model_id,
                "budget_contract_sha256": self.contract_sha,
                "currency": "GBP",
                "role": role,
                "role_create_ordinal": role_ordinal,
                "aggregate_create_ordinal": aggregate_ordinal,
                "request_bytes": request_bytes,
                "input_token_upper_bound": input_upper,
                "input_bound_source": input_bound_source,
                "input_token_reservation": input_upper,
                "max_output_tokens": requested_output,
                "request_max_output_tokens": request_output,
                "output_bound_source": output_bound_source,
                "long_context_surcharge_applied": input_upper > FRONTIER_LONG_CONTEXT_THRESHOLD_TOKENS,
                "pricing_reference": FRONTIER_PRICING_REFERENCE,
                "reserved_gbp": _decimal_text(reservation),
                "running_reserved_gbp": _decimal_text(next_reserved),
                "total_cap_gbp": _decimal_text(self.contract.total_cap_gbp),
                "reservation_refundable": False,
                "usage_settlement_eligible": self.contract.schema_version == BUDGET_SCHEMA_V2,
            }
            try:
                self._append_journal(event)
            except Exception as exc:
                raise ProviderBudgetError(
                    f"provider budget journal write failed before dispatch: {type(exc).__name__}: {exc}"
                ) from exc
            self._role_counts[role] += 1
            self._total_count += 1
            self._reserved_gbp = next_reserved
            self._reservations[aggregate_ordinal] = {
                "role": role,
                "role_create_ordinal": role_ordinal,
                "aggregate_create_ordinal": aggregate_ordinal,
                "input_token_upper_bound": input_upper,
                "max_output_tokens": requested_output,
                "reserved_gbp": reservation,
                "settled": False,
            }
            return dict(event)

    def settle_success(
        self,
        reservation: Mapping[str, Any] | int,
        *,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, Any]:
        """Settle one v2 provisional reservation from authoritative success usage.

        This is not a generic refund path. V1 never settles. V2 only releases
        the difference between the original conservative pre-dispatch hold and
        a still-conservative charge computed from provider-reported terminal
        success usage. Any usage inconsistency leaves the full hold intact.
        """
        if self.contract.schema_version != BUDGET_SCHEMA_V2:
            raise ProviderBudgetError("provider budget settlement is only valid for v2 contracts")
        try:
            aggregate_ordinal = int(
                reservation.get("aggregate_create_ordinal")
                if isinstance(reservation, Mapping) else reservation
            )
            actual_input = int(input_tokens)
            actual_output = int(output_tokens)
        except (TypeError, ValueError) as exc:
            raise ProviderBudgetError("provider budget settlement usage/identity must be integer") from exc
        if actual_input < 0 or actual_output < 0:
            raise ProviderBudgetError("provider budget settlement usage must be non-negative")
        with self._lock:
            record = self._reservations.get(aggregate_ordinal)
            if record is None:
                raise ProviderBudgetError("provider budget settlement references unknown reservation")
            if record.get("settled"):
                raise ProviderBudgetError("provider budget reservation settled more than once")
            if actual_input > int(record["input_token_upper_bound"]):
                raise ProviderBudgetError("provider budget settlement input usage exceeds reservation bound")
            if actual_output > int(record["max_output_tokens"]):
                raise ProviderBudgetError("provider budget settlement output usage exceeds reservation bound")
            role = str(record["role"])
            row = self.contract.roles[role]
            settled = reservation_gbp(
                row, input_tokens=actual_input, output_tokens=actual_output,
            )
            original = Decimal(record["reserved_gbp"])
            if settled > original:
                raise ProviderBudgetError("provider budget settlement exceeds original reservation")
            released = original - settled
            next_reserved = self._reserved_gbp - released
            if next_reserved < 0:
                raise ProviderBudgetError("provider budget settlement would make running reservation negative")
            event = {
                "schema_version": "aether.provider_budget_settlement.v1",
                "budget_id": self.contract.budget_id,
                "model_id": self.contract.model_id,
                "budget_contract_sha256": self.contract_sha,
                "currency": "GBP",
                "role": role,
                "role_create_ordinal": int(record["role_create_ordinal"]),
                "aggregate_create_ordinal": aggregate_ordinal,
                "provider_input_tokens": actual_input,
                "provider_output_tokens": actual_output,
                "usage_source": "provider_reported_terminal_success",
                "pricing_reference": FRONTIER_PRICING_REFERENCE,
                "original_reserved_gbp": _decimal_text(original),
                "settled_gbp": _decimal_text(settled),
                "released_provisional_gbp": _decimal_text(released),
                "running_reserved_gbp": _decimal_text(next_reserved),
                "total_cap_gbp": _decimal_text(self.contract.total_cap_gbp),
            }
            try:
                self._append_journal(event)
            except Exception as exc:
                raise ProviderBudgetError(
                    f"provider budget settlement journal write failed: {type(exc).__name__}: {exc}"
                ) from exc
            record["settled"] = True
            record["settled_gbp"] = settled
            record["released_provisional_gbp"] = released
            self._reserved_gbp = next_reserved
            self._settlement_count += 1
            return dict(event)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "budget_id": self.contract.budget_id,
                "model_id": self.contract.model_id,
                "budget_contract_sha256": self.contract_sha,
                "currency": "GBP",
                "role_create_counts": dict(self._role_counts),
                "aggregate_create_count": self._total_count,
                "settlement_count": self._settlement_count,
                "unsettled_reservation_count": sum(
                    1 for row in self._reservations.values() if not row.get("settled")
                ),
                "reserved_gbp": _decimal_text(self._reserved_gbp),
                "total_cap_gbp": _decimal_text(self.contract.total_cap_gbp),
            }


_GUARDS_LOCK = threading.Lock()
_GUARDS: dict[tuple[str, str], ProviderBudgetGuard] = {}


def provider_budget_guard_from_env(*, expected_model_id: str = "gpt-5.6-luna") -> ProviderBudgetGuard | None:
    contract = budget_contract_from_env()
    if contract is None:
        return None
    if contract.model_id != expected_model_id:
        raise ProviderBudgetError("provider budget model_id does not match selected route")
    raw_path = str(Path(os.environ[BUDGET_PATH_ENV]).expanduser().resolve(strict=True))
    contract_sha = str(os.environ[BUDGET_SHA256_ENV]).strip().lower()
    key = (raw_path, contract_sha)
    with _GUARDS_LOCK:
        guard = _GUARDS.get(key)
        if guard is None:
            guard = ProviderBudgetGuard(
                contract,
                contract_sha=contract_sha,
                journal_path=str(os.environ.get(BUDGET_JOURNAL_ENV, "") or "").strip() or None,
            )
            _GUARDS[key] = guard
        return guard


def budget_runtime_limits_from_env() -> dict[str, Any] | None:
    contract = budget_contract_from_env()
    if contract is None:
        return None
    return {
        "budget_id": contract.budget_id,
        "model_id": contract.model_id,
        "budget_contract_sha256": contract.sha256(),
        "budget_schema_version": contract.schema_version,
        "solver_turn_budget": contract.solver_turn_budget,
        "agent_timeout_sec": contract.agent_timeout_sec,
        "solver_max_output_tokens": contract.runtime_max_output_tokens.get("solver"),
        "verifier_max_output_tokens": contract.runtime_max_output_tokens.get("verifier"),
        "vision_max_output_tokens": contract.runtime_max_output_tokens.get("vision"),
        "provider_max_retries": contract.provider_max_retries,
        "provider_sdk_max_retries": contract.provider_sdk_max_retries,
        "max_total_provider_creates": contract.max_total_provider_creates,
        "total_cap_gbp": _decimal_text(contract.total_cap_gbp),
        "theoretical_ceiling_product_gbp": _decimal_text(contract.worst_case_total_gbp),
        "vm_incremental_cap_gbp": _decimal_text(contract.vm_incremental_cap_gbp),
    }


def clear_provider_budget_guard_cache_for_tests() -> None:
    with _GUARDS_LOCK:
        _GUARDS.clear()
