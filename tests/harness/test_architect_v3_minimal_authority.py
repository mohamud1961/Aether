from __future__ import annotations

from copy import deepcopy
import json

import pytest

from aether.architect_v3_contract import (
    V3_SCHEMA_VERSION,
    architect_v3_json_schema,
    architect_v3_provider_schema,
    project_architect_v3_runtime,
    project_architect_v3_shadow,
    validate_architect_v3,
)
from aether.architect_v3_model import (
    ARCHITECT_V3_SYSTEM_PROMPT,
    ArchitectV3Model,
    architect_v3_source_catalog,
    architect_v3_source_contents,
    build_architect_v3_model_request,
)
from aether.model_hooks import ModelOutputError
from aether.runtime_ir import EnvMap


SOURCE_CATALOG = {
    "user_task": "task_prompt",
    "workspace": "visible_environment",
}
SOURCE_CONTENTS = {
    "user_task": "Run the service using server_ok.py on port 8080.",
    "workspace": {"file_tree": "server_ok.py\nREADME.md"},
}


def _parameter(parameter_id: str, value, source_text: str, source: str = "user_task") -> dict:
    return {
        "parameter_id": parameter_id,
        "value": value,
        "source_text": source_text,
        "source_refs": [source],
    }


def _payload() -> dict:
    return {
        "schema_version": V3_SCHEMA_VERSION,
        "outcomes": [
            {
                "outcome_id": "service_available",
                "description": "The service accepts requests on the required port.",
                "parameters": [
                    _parameter("required_port", 8080, "8080"),
                ],
                "source_refs": ["user_task"],
            }
        ],
        "constraints": [
            {
                "constraint_id": "required_launcher_constraint",
                "kind": "required_method",
                "description": "The service is launched using the required launcher.",
                "applies_to": ["service_available"],
                "parameters": [
                    _parameter("required_launcher", "server_ok.py", "server_ok.py"),
                ],
                "source_refs": ["user_task"],
            }
        ],
        "proof_facets": [
            {
                "proof_id": "service_public_behavior",
                "target_type": "outcome",
                "target_id": "service_available",
                "proof_kind": "public_behavior",
                "acceptance_observation": "A fresh request to the required port succeeds.",
                "falsification_observation": "A fresh request fails or reaches the wrong service.",
            },
            {
                "proof_id": "launcher_constraint_compliance",
                "target_type": "constraint",
                "target_id": "required_launcher_constraint",
                "proof_kind": "exact_state",
                "acceptance_observation": "Immutable execution evidence identifies the required launcher.",
                "falsification_observation": "Execution evidence identifies another launcher or no launcher.",
            },
        ],
        "solver_strategy": {
            "approach": [
                {
                    "strategy_id": "separate_behavior_and_launcher",
                    "guidance": "Treat live service behavior and required-launcher compliance as distinct relationships while adapting to the observed runtime.",
                    "uncertainty": "Whether the active service was launched by the required launcher and serves the required endpoint.",
                    "outcome_refs": ["service_available"],
                    "constraint_refs": ["required_launcher_constraint"],
                    "proof_refs": [
                        "service_public_behavior",
                        "launcher_constraint_compliance",
                    ],
                }
            ]
        },
    }


def _validate(payload: dict):
    return validate_architect_v3(
        payload,
        source_catalog=SOURCE_CATALOG,
        source_contents=SOURCE_CONTENTS,
    )


def _pilot_payload() -> dict:
    payload = _payload()
    payload.pop("solver_strategy")
    for proof in payload["proof_facets"]:
        proof["insufficient_proxies"] = [
            "A local status or metadata observation without the required relationship."
        ]
    payload["pilot_briefing"] = {
        "mission": (
            "Bring the public service behavior and the explicitly mandated launcher "
            "relationship into agreement, then preserve both proof boundaries."
        ),
        "priorities": [
            "service_available",
            "required_launcher_constraint",
        ],
        "uncertainties": [
            "Whether the active service owns the required endpoint and the required launcher relationship."
        ],
        "adaptive_strategy": [
            {
                "guidance": (
                    "Keep public behavior and launcher compliance as separate relationships "
                    "while adapting to observed state."
                ),
                "serves": [
                    "service_available",
                    "required_launcher_constraint",
                    "service_public_behavior",
                    "launcher_constraint_compliance",
                ],
                "pivot_when": (
                    "If direct observations disagree, preserve the failing relationship "
                    "as the active uncertainty rather than assuming the other one."
                ),
            }
        ],
    }
    return payload


def test_v3_validates_owner_local_parameters_and_minimal_authority() -> None:
    contract = _validate(_payload())
    assert contract.outcome_ids == ("service_available",)
    assert contract.constraint_ids == ("required_launcher_constraint",)
    assert contract.proof_ids == (
        "service_public_behavior",
        "launcher_constraint_compliance",
    )
    assert contract.parameter_ids == (
        "outcome:service_available:required_port",
        "constraint:required_launcher_constraint:required_launcher",
    )
    assert set(contract.payload) == {
        "schema_version",
        "outcomes",
        "constraints",
        "proof_facets",
        "solver_strategy",
    }
    assert "facts" not in contract.payload


def test_v3_rejects_generic_parameter_ids() -> None:
    raw = _payload()
    raw["outcomes"][0]["parameters"][0]["parameter_id"] = "f1"
    with pytest.raises(ModelOutputError, match="generic numbered IDs"):
        _validate(raw)


def test_v3_rejects_ungrounded_or_unbound_parameter_data() -> None:
    wrong_span = _payload()
    wrong_span["outcomes"][0]["parameters"][0]["source_text"] = "port 9999"
    with pytest.raises(ModelOutputError, match="value must occur in source_text"):
        _validate(wrong_span)

    absent_source = _payload()
    absent_source["outcomes"][0]["parameters"][0].update({
        "value": 9999,
        "source_text": "9999",
    })
    with pytest.raises(ModelOutputError, match="not present in cited"):
        _validate(absent_source)


def test_v3_rejects_constraint_grounded_only_in_environment() -> None:
    raw = _payload()
    raw["constraints"][0]["source_refs"] = ["workspace"]
    raw["constraints"][0]["parameters"][0] = _parameter(
        "required_launcher",
        "server_ok.py",
        "server_ok.py",
        "workspace",
    )
    with pytest.raises(ModelOutputError, match="explicit task or visible-material"):
        _validate(raw)


def test_v3_rejects_task_wording_as_constraint_compliance_evidence() -> None:
    raw = _payload()
    raw["proof_facets"][1]["acceptance_observation"] = (
        "The task prompt explicitly requires server_ok.py."
    )
    with pytest.raises(ModelOutputError, match="task wording as constraint-compliance"):
        _validate(raw)


def test_v3_requires_direct_proof_for_every_outcome_and_constraint() -> None:
    missing_constraint = _payload()
    missing_constraint["proof_facets"] = missing_constraint["proof_facets"][:1]
    with pytest.raises(ModelOutputError, match="do not cover constraints"):
        _validate(missing_constraint)

    missing_outcome = _payload()
    missing_outcome["proof_facets"] = missing_outcome["proof_facets"][1:]
    with pytest.raises(ModelOutputError, match="do not cover outcomes"):
        _validate(missing_outcome)


def test_v3_solver_strategy_is_bounded_bound_and_single_line() -> None:
    too_many = _payload()
    row = deepcopy(too_many["solver_strategy"]["approach"][0])
    too_many["solver_strategy"]["approach"] = [
        {**deepcopy(row), "strategy_id": f"strategy_{index}"}
        for index in range(5)
    ]
    with pytest.raises(ModelOutputError, match="at most 4"):
        _validate(too_many)

    unbound = _payload()
    unbound["solver_strategy"]["approach"][0].update({
        "outcome_refs": [],
        "constraint_refs": [],
        "proof_refs": [],
    })
    with pytest.raises(ModelOutputError, match="must reference at least one"):
        _validate(unbound)

    multiline = _payload()
    multiline["solver_strategy"]["approach"][0]["uncertainty"] = (
        "Which launcher is active?\nWhether it owns the service."
    )
    with pytest.raises(ModelOutputError, match="one short line"):
        _validate(multiline)


def test_v3_shadow_projection_is_mechanical_and_owner_bound() -> None:
    projection = project_architect_v3_shadow(
        _payload(),
        source_catalog=SOURCE_CATALOG,
        source_contents=SOURCE_CONTENTS,
    )
    assert projection.status == "shadow_only"
    assert projection.requirements_identity
    assert [item.proof_id for item in projection.requirements] == [
        "service_public_behavior",
        "launcher_constraint_compliance",
    ]
    assert projection.proof_targets == (
        ("service_public_behavior", "outcome", "service_available"),
        (
            "launcher_constraint_compliance",
            "constraint",
            "required_launcher_constraint",
        ),
    )
    assert "required_port=8080" in projection.solver_prompt
    assert "required_launcher='server_ok.py'" in projection.solver_prompt
    assert "[Architect v3 solver strategy]" in projection.solver_prompt
    assert "launch_process" not in projection.solver_prompt


def test_v3_pilot_briefing_and_proxy_evidence_project_to_both_roles() -> None:
    contract = _validate(_pilot_payload())
    projection = project_architect_v3_runtime(contract)

    assert "pilot_briefing" in contract.payload
    assert "[Architect v3 Solver pilot briefing]" in projection.solver_prompt
    assert "Bring the public service behavior" in projection.solver_prompt
    assert (
        "Priorities (ordered authority IDs; preserve this order): "
        "service_available, required_launcher_constraint"
    ) in projection.solver_prompt
    assert "The Verifier remains neutral" in projection.verifier_prompt
    assert "Insufficient proxies:" in projection.verifier_prompt
    assert projection.requirements[0].insufficient_proxies == (
        "A local status or metadata observation without the required relationship.",
    )
    assert projection.requirements[1].insufficient_proxies
    compiled = projection.requirements[0].as_dict()
    assert compiled["insufficient_proxies"]
    assert "insufficient_proxy_evidence" not in compiled


def test_v3_pilot_briefing_accepts_ordered_authority_ids() -> None:
    payload = _pilot_payload()
    payload["pilot_briefing"]["priorities"] = [
        "required_launcher_constraint",
        "service_available",
    ]

    contract = _validate(payload)

    assert contract.payload["pilot_briefing"]["priorities"] == [
        "required_launcher_constraint",
        "service_available",
    ]


def test_v3_pilot_briefing_rejects_natural_language_priority_prose() -> None:
    payload = _pilot_payload()
    payload["pilot_briefing"]["priorities"] = [
        "Prioritize the live set/get round trip before other concerns."
    ]

    with pytest.raises(
        ModelOutputError,
        match="must contain v3 authority IDs, not natural-language prose",
    ):
        _validate(payload)


def test_v3_pilot_briefing_requires_proxy_evidence() -> None:
    payload = _pilot_payload()
    payload["proof_facets"][0].pop("insufficient_proxies")
    with pytest.raises(ModelOutputError, match="must include insufficient_proxies"):
        _validate(payload)


def test_v3_pilot_briefing_rejects_exact_action_mechanics() -> None:
    payload = _pilot_payload()
    payload["pilot_briefing"]["adaptive_strategy"][0]["guidance"] = (
        "Run python3 verify.py before relying on the service state."
    )
    with pytest.raises(ModelOutputError, match="prescribes an exact action"):
        _validate(payload)


@pytest.mark.parametrize(
    "observed_condition",
    (
        "The image does not visibly read as a centered red square on a white background.",
        "The artifact is present but not at the specified path.",
        "Observed evidence suggests the API became ready before the database or readiness is not externally observable.",
        "The current execution record cannot distinguish which service started first.",
        "Only process presence or open connectivity is observable without readiness confirmation.",
    ),
)
def test_v3_pivot_when_accepts_observed_state_language_from_live_failures(
    observed_condition: str,
) -> None:
    payload = _pilot_payload()
    payload["pilot_briefing"]["adaptive_strategy"][0]["pivot_when"] = observed_condition

    contract = _validate(payload)

    assert (
        contract.payload["pilot_briefing"]["adaptive_strategy"][0]["pivot_when"]
        == observed_condition
    )


@pytest.mark.parametrize(
    "prescription",
    (
        "Run python3 verify.py before relying on the service state.",
        "If observations disagree, run python3 verify.py.",
        "The Solver should open /app/output.png.",
        "Adapt by running python3 verify.py.",
        "Preserve the current hypothesis, then open /app/output.png.",
    ),
)
def test_v3_pivot_when_rejects_prescriptive_action_grammar(
    prescription: str,
) -> None:
    payload = _pilot_payload()
    payload["pilot_briefing"]["adaptive_strategy"][0]["pivot_when"] = prescription

    with pytest.raises(ModelOutputError, match="prescribes an exact action"):
        _validate(payload)


def test_v3_validation_does_not_mutate_caller_payload() -> None:
    payload = _pilot_payload()
    payload["proof_facets"][0]["insufficient_proxy_evidence"] = payload[
        "proof_facets"][0].pop("insufficient_proxies")
    original = deepcopy(payload)

    contract = _validate(payload)

    assert payload == original
    assert "insufficient_proxy_evidence" in contract.payload["proof_facets"][0]


def test_v3_schema_has_no_global_fact_or_v2_dumping_ground_fields() -> None:
    canonical = architect_v3_json_schema()
    provider = architect_v3_provider_schema()
    expected = {
        "schema_version",
        "outcomes",
        "constraints",
        "proof_facets",
        "pilot_briefing",
    }
    assert set(canonical["properties"]) == expected
    assert set(provider["properties"]) == expected
    rendered = json.dumps(canonical, sort_keys=True)
    rendered_provider = json.dumps(provider, sort_keys=True)
    assert '"pilot_briefing"' in rendered_provider
    assert "solver_strategy" not in rendered_provider
    assert "insufficient_proxy_evidence" not in rendered_provider
    for forbidden in (
        '"facts"',
        "required_environment",
        "solver_design",
        "verifier_design",
        "false_positive_risks",
        "information_emphasis",
        "method_constraints",
        "task_contract",
    ):
        assert forbidden not in rendered


def test_v3_model_facing_priority_contract_requires_ordered_authority_ids() -> None:
    normalized_prompt = " ".join(ARCHITECT_V3_SYSTEM_PROMPT.split())
    assert "ordered `priorities` are authority IDs" in normalized_prompt
    assert "each exactly one existing `outcome_id`, `constraint_id`, or `proof_id`" in normalized_prompt
    assert "Do not write natural-language priority descriptions" in normalized_prompt
    assert "1–4 uncertainties and 1–4 adaptive strategy rows" in normalized_prompt
    assert "adaptive cognitive guidance, served IDs, and pivot_when" in normalized_prompt

    provider = architect_v3_provider_schema()
    briefing = provider["properties"]["pilot_briefing"]
    priorities = briefing["properties"]["priorities"]
    assert "existing v3 authority IDs" in priorities["description"]
    assert "Do not put natural-language priority descriptions here" in priorities["description"]


def test_v3_request_is_raw_source_tagged_not_preclassified() -> None:
    envmap = EnvMap(
        task_prompt="Run the service using server_ok.py on port 8080.",
        workspace_root="/app",
        visible_files=("/app/server_ok.py",),
        file_tree="server_ok.py\nREADME.md",
        file_map_summary={"top_level": ["server_ok.py", "README.md"]},
        services={"candidate": {"port": 8080}},
    )
    request = build_architect_v3_model_request(envmap)
    assert request["schema_version"] == "architect_v3_request.v2"
    assert request["runtime_protocol"]["completion_signal_owner"] == (
        "solver submit_outcome protocol"
    )
    assert "named external artifact" in request["runtime_protocol"][
        "completion_language_rule"
    ]
    assert architect_v3_source_catalog(request)["user_task"] == "task_prompt"
    assert architect_v3_source_contents(request)["user_task"] == (
        "Run the service using server_ok.py on port 8080."
    )
    rendered = json.dumps(request, sort_keys=True)
    assert "workspace_root" not in rendered
    assert "capability_availability" not in rendered
    for forbidden in (
        "outcome_candidate",
        "method_candidate",
        "exact_fact",
        "obligation_candidate",
    ):
        assert forbidden not in rendered


def test_v3_model_is_one_call_and_strict_without_correction() -> None:
    calls: list[tuple[list[dict[str, str]], int]] = []

    def model(messages, *, max_output_tokens):
        calls.append((messages, max_output_tokens))
        return deepcopy(_payload())

    request = {
        "schema_version": "architect_v3_request.v2",
        "request_identity": {"envmap_digest": "abc"},
        "sources": [
            {
                "source_id": "user_task",
                "source_type": "task_prompt",
                "content": SOURCE_CONTENTS["user_task"],
            },
            {
                "source_id": "workspace",
                "source_type": "visible_environment",
                "content": SOURCE_CONTENTS["workspace"],
            },
        ],
    }
    result = ArchitectV3Model(model).configure(request)
    assert result.valid
    assert result.call_count == 1
    assert len(calls) == 1


def test_v3_model_fails_closed_after_one_invalid_response() -> None:
    calls = 0

    def model(messages, *, max_output_tokens):
        nonlocal calls
        calls += 1
        return {"schema_version": V3_SCHEMA_VERSION}

    request = {
        "schema_version": "architect_v3_request.v2",
        "request_identity": {"envmap_digest": "abc"},
        "sources": [
            {
                "source_id": "user_task",
                "source_type": "task_prompt",
                "content": "Create output.txt.",
            }
        ],
    }
    result = ArchitectV3Model(model).configure(request)
    assert not result.valid
    assert result.call_count == 1
    assert calls == 1


def test_v3_model_prompt_preserves_cognitive_and_execution_boundary() -> None:
    prompt = ARCHITECT_V3_SYSTEM_PROMPT
    assert "The Solver owns concrete execution" in prompt
    assert "owner-local parameters" in prompt
    assert "generic IDs such as f1 are" in prompt
    assert "invalid" in prompt
    normalized_prompt = " ".join(prompt.split())
    assert "shortest exact span" in normalized_prompt
    assert "A successful public operation does not prove" in prompt
    assert "Apply outcome subsumption" in prompt
    assert "run/start/launch X so Y" in prompt
    assert "fresh request" in prompt
    assert "immutable action history" in prompt
    assert "launcher identity" in prompt
    assert "Logs, receipts, process tables" in prompt
    assert "listen on port 5328" in prompt
    assert "run using server_ok.py" in prompt
    assert "configure the route using /etc/nginx/conf.d/default.conf" in prompt
    assert "without X" in prompt
    assert "prohibited_method" in prompt
    assert "if a different method" in prompt
    assert "Write config.yaml" in prompt
    assert "task prompt or" in prompt
    assert "Phrase unobserved state as a hypothesis" in prompt
    assert "change all concrete actions while still following the strategy" in prompt
    assert "Apply runtime_protocol completion ownership" in prompt
    assert "submit_outcome protocol, not a task outcome" in " ".join(prompt.split())


def test_v3_model_facing_contract_uses_perception_when_content_recognition_is_decisive() -> None:
    schema_text = json.dumps(architect_v3_provider_schema(), sort_keys=True)
    assert "requires recognising content" in schema_text
    assert "do not choose exact_state merely because" in ARCHITECT_V3_SYSTEM_PROMPT.casefold()


def test_v3_parameters_reject_boolean_abstractions() -> None:
    payload = _payload()
    payload["outcomes"][0]["parameters"].append({
        "parameter_id": "post_exit_persistence",
        "value": True,
        "source_text": "keep running after the agent loop exits",
        "source_refs": ["user_task"],
    })
    with pytest.raises(ModelOutputError, match="booleans and containers are forbidden"):
        validate_architect_v3(payload, source_catalog=SOURCE_CATALOG, source_contents=SOURCE_CONTENTS)


def test_v3_parameter_schema_allows_only_strings_and_numbers() -> None:
    schema = architect_v3_json_schema()
    value_schema = (
        schema["properties"]["outcomes"]["items"]["properties"]
        ["parameters"]["items"]["properties"]["value"]
    )
    assert {row.get("type") for row in value_schema["anyOf"]} == {"string", "number"}
    assert "boolean" not in {row.get("type") for row in value_schema["anyOf"]}


def test_v3_prompt_keeps_relations_out_of_parameter_values() -> None:
    prompt = ARCHITECT_V3_SYSTEM_PROMPT
    assert "Never encode a relationship as a boolean" in prompt
    assert "Put relational meaning in the owning description" in prompt


def test_v3_prompt_requires_verbatim_markdown_source_spans() -> None:
    prompt = ARCHITECT_V3_SYSTEM_PROMPT
    assert "source_text must be copied verbatim" in prompt
    assert "Preserve Markdown" in prompt
    assert "Do not normalize" in prompt


def test_v3_prompt_never_adds_markdown_delimiters() -> None:
    prompt = " ".join(ARCHITECT_V3_SYSTEM_PROMPT.split())
    assert "never add formatting delimiters" in prompt
    assert "not an invented inline-code wrapper" in prompt
    assert "underlying task value without presentation-only Markdown" in prompt


def test_v3_canonicalizes_only_invented_single_backtick_wrappers() -> None:
    payload = _payload()
    parameter = payload["outcomes"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "required_line",
        "value": "status: ready",
        "source_text": "`status: ready`",
    })
    original = deepcopy(payload)
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = SOURCE_CONTENTS["user_task"] + "\nCreate report.txt containing exactly:\n```\nstatus: ready\n```"
    contract = validate_architect_v3(
        payload, source_catalog=SOURCE_CATALOG, source_contents=contents,
    )
    canonical = contract.payload["outcomes"][0]["parameters"][0]
    assert canonical["source_text"] == "status: ready"
    assert canonical["value"] == "status: ready"
    assert payload == original


def test_v3_preserves_real_inline_code_backticks() -> None:
    payload = _payload()
    parameter = payload["outcomes"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "response_body",
        "value": "ok",
        "source_text": "`ok`",
    })
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = SOURCE_CONTENTS["user_task"] + "\nThe response must be exactly `ok`."
    contract = validate_architect_v3(
        payload, source_catalog=SOURCE_CATALOG, source_contents=contents,
    )
    canonical = contract.payload["outcomes"][0]["parameters"][0]
    assert canonical["source_text"] == "`ok`"


def test_v3_does_not_use_backtick_canonicalization_for_paraphrase() -> None:
    payload = _payload()
    parameter = payload["outcomes"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "required_line",
        "value": "status ready",
        "source_text": "`status ready`",
    })
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = SOURCE_CONTENTS["user_task"] + "\nCreate report.txt containing status: ready."
    with pytest.raises(ModelOutputError, match="not present in cited model-visible sources"):
        validate_architect_v3(
            payload, source_catalog=SOURCE_CATALOG, source_contents=contents,
        )


def test_v3_canonicalizes_invented_phrase_around_distinctive_literal() -> None:
    payload = _payload()
    parameter = payload["constraints"][0]["parameters"][0]
    parameter["source_text"] = "server `server_ok.py`"
    contract = validate_architect_v3(
        payload,
        source_catalog=SOURCE_CATALOG,
        source_contents=SOURCE_CONTENTS,
    )
    assert contract.payload["constraints"][0]["parameters"][0]["source_text"] == "server_ok.py"


def test_v3_does_not_canonicalize_ambiguous_small_scalar_binding() -> None:
    payload = _payload()
    parameter = payload["outcomes"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "request_field_number",
        "value": 2,
        "source_text": "field number 2",
    })
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = SOURCE_CONTENTS["user_task"] + " Request field 2; response field 1."
    with pytest.raises(ModelOutputError, match="source_text is not present"):
        validate_architect_v3(
            payload,
            source_catalog=SOURCE_CATALOG,
            source_contents=contents,
        )



def test_v3_value_may_exclude_inline_code_delimiters_from_verbatim_span() -> None:
    payload = _payload()
    parameter = payload["constraints"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "verification_requirement",
        "value": "exactly ok",
        "source_text": "verify the service responds exactly `ok`",
    })
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = (
        SOURCE_CONTENTS["user_task"]
        + " Before completion, verify the service responds exactly `ok`."
    )
    contract = validate_architect_v3(
        payload,
        source_catalog=SOURCE_CATALOG,
        source_contents=contents,
    )
    grounded = contract.payload["constraints"][0]["parameters"][0]
    assert grounded["value"] == "exactly ok"
    assert grounded["source_text"] == "verify the service responds exactly `ok`"


def test_v3_inline_code_grounding_does_not_normalize_other_markdown_or_prose() -> None:
    payload = _payload()
    parameter = payload["constraints"][0]["parameters"][0]
    parameter.update({
        "parameter_id": "verification_requirement",
        "value": "verification ok",
        "source_text": "verify the service responds exactly `ok`",
    })
    contents = dict(SOURCE_CONTENTS)
    contents["user_task"] = (
        SOURCE_CONTENTS["user_task"]
        + " Before completion, verify the service responds exactly `ok`."
    )
    with pytest.raises(ModelOutputError, match="value must occur in source_text"):
        validate_architect_v3(
            payload,
            source_catalog=SOURCE_CATALOG,
            source_contents=contents,
        )
