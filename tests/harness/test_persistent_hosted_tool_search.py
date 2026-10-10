from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from aether.persistent_hosted_tool_search import (
    HostedToolSearchError,
    HostedToolSearchState,
    catalogue_identity,
    hosted_provider_tools,
    validate_hosted_response,
)
from aether.persistent_provider_protocol import PERSISTENT_DIRECT_PROVIDER_TOOLS


def _tool(name: str, *, value: str = "x") -> dict:
    return {
        "type": "function",
        "name": name,
        "description": f"tool {name}",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["arguments"],
            "properties": {
                "arguments": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["value"],
                    "properties": {"value": {"type": "string", "enum": [value]}},
                }
            },
        },
        "strict": True,
    }


def _response(*items, response_id: str = "resp-1"):
    return SimpleNamespace(id=response_id, status="completed", output=list(items))


def _search_pair(*loaded):
    return (
        SimpleNamespace(
            type="tool_search_call", execution="server", call_id=None,
            status="completed", arguments={"paths": ["read_file"]},
        ),
        SimpleNamespace(
            type="tool_search_output", execution="server", call_id=None,
            status="completed", tools=list(loaded),
        ),
    )


def _function(name: str):
    return SimpleNamespace(
        type="function_call", id="fc-1", call_id="call-1", name=name,
        arguments='{"arguments":{"value":"x"}}',
    )


def test_hosted_projection_defers_actions_but_pins_completion() -> None:
    rendered, catalogue = hosted_provider_tools(PERSISTENT_DIRECT_PROVIDER_TOOLS)
    by_name = {
        str(tool.get("name")): tool for tool in rendered
        if tool.get("type") == "function"
    }
    assert {"finish_intent", "finish"}.issubset(by_name)
    assert "defer_loading" not in by_name["finish_intent"]
    assert "defer_loading" not in by_name["finish"]
    assert "finish_intent" not in catalogue and "finish" not in catalogue
    assert catalogue
    assert all(tool.get("defer_loading") is True for tool in catalogue.values())
    assert [tool for tool in rendered if tool.get("type") == "tool_search"] == [
        {"type": "tool_search"}
    ]


def test_catalogue_identity_is_order_stable_and_schema_sensitive() -> None:
    a = _tool("alpha")
    b = _tool("beta")
    a["defer_loading"] = True
    b["defer_loading"] = True
    one = catalogue_identity({"alpha": a, "beta": b})
    two = catalogue_identity({"beta": deepcopy(b), "alpha": deepcopy(a)})
    assert one == two
    changed = deepcopy(b)
    changed["description"] = "changed"
    assert catalogue_identity({"alpha": a, "beta": changed})["sha256"] != one["sha256"]


def test_hosted_response_accepts_exact_server_loaded_schema_and_one_call() -> None:
    declared = _tool("alpha")
    rendered, catalogue = hosted_provider_tools([declared])
    loaded = deepcopy(catalogue["alpha"])
    search_call, search_output = _search_pair(loaded)
    observation = validate_hosted_response(
        _response(search_call, search_output, _function("alpha")),
        catalogue=catalogue,
    )
    assert observation.newly_loaded_names == ("alpha",)
    assert observation.executable_deferred_names == ("alpha",)
    assert observation.callable_deferred_names_after_response == ("alpha",)
    assert observation.search_call_count == observation.search_output_count == 1
    assert observation.catalogue_sha256 == catalogue_identity(catalogue)["sha256"]
    assert any(tool.get("type") == "tool_search" for tool in rendered)


def test_previously_committed_tool_can_be_called_without_new_search() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    observation = validate_hosted_response(
        _response(_function("alpha")),
        catalogue=catalogue,
        committed_loaded_names=("alpha",),
    )
    assert observation.search_call_count == 0
    assert observation.newly_loaded_names == ()
    assert observation.executable_deferred_names == ("alpha",)


def test_deferred_call_without_current_or_committed_load_fails_closed() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    with pytest.raises(HostedToolSearchError, match="deferred_call_not_loaded"):
        validate_hosted_response(_response(_function("alpha")), catalogue=catalogue)


def test_loaded_schema_digest_mismatch_fails_closed() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    tampered = deepcopy(catalogue["alpha"])
    tampered["description"] = "provider rewrote schema"
    search_call, search_output = _search_pair(tampered)
    with pytest.raises(HostedToolSearchError, match="loaded_schema_digest_mismatch"):
        validate_hosted_response(
            _response(search_call, search_output, _function("alpha")),
            catalogue=catalogue,
        )


def test_loaded_unknown_tool_and_nonserver_search_fail_closed() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    unknown = _tool("beta")
    unknown["defer_loading"] = True
    call, output = _search_pair(unknown)
    with pytest.raises(HostedToolSearchError, match="loaded_tool_not_declared"):
        validate_hosted_response(_response(call, output), catalogue=catalogue)

    bad_call = SimpleNamespace(
        type="tool_search_call", execution="client", call_id="client-1",
        status="completed", arguments={},
    )
    good_output = SimpleNamespace(
        type="tool_search_output", execution="server", call_id=None,
        status="completed", tools=[],
    )
    with pytest.raises(HostedToolSearchError, match="execution_invalid"):
        validate_hosted_response(_response(bad_call, good_output), catalogue=catalogue)


def test_search_pair_count_and_committed_catalogue_drift_fail_closed() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    call, _output = _search_pair()
    with pytest.raises(HostedToolSearchError, match="pair_count_invalid"):
        validate_hosted_response(_response(call), catalogue=catalogue)
    with pytest.raises(HostedToolSearchError, match="committed_catalogue_drift"):
        validate_hosted_response(
            _response(), catalogue=catalogue, committed_loaded_names=("missing",),
        )


def test_state_commit_reject_and_parent_loss_clear_are_transactional() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha"), _tool("beta")])
    call, output = _search_pair(deepcopy(catalogue["alpha"]))
    obs_a = validate_hosted_response(
        _response(call, output, _function("alpha")), catalogue=catalogue,
    )
    state = HostedToolSearchState()
    state.stage_candidate(
        run_id="run", task_id="task", response_id="resp-a", observation=obs_a,
    )
    assert state.committed_loaded_names(run_id="run", task_id="task") == ()
    state.reject_candidate(run_id="run", task_id="task", response_id="resp-a")
    assert state.committed_loaded_names(run_id="run", task_id="task") == ()

    state.stage_candidate(
        run_id="run", task_id="task", response_id="resp-a2", observation=obs_a,
    )
    assert state.commit_candidate(
        run_id="run", task_id="task", response_id="resp-a2"
    ) == ("alpha",)

    call2, output2 = _search_pair(deepcopy(catalogue["beta"]))
    obs_b = validate_hosted_response(
        _response(call2, output2, _function("beta"), response_id="resp-b"),
        catalogue=catalogue,
        committed_loaded_names=("alpha",),
    )
    state.stage_candidate(
        run_id="run", task_id="task", response_id="resp-b", observation=obs_b,
    )
    assert state.commit_candidate(
        run_id="run", task_id="task", response_id="resp-b"
    ) == ("alpha", "beta")

    state.clear_scope(run_id="run", task_id="task")
    assert state.committed_loaded_names(run_id="run", task_id="task") == ()


def test_completion_function_never_requires_search_load() -> None:
    _rendered, catalogue = hosted_provider_tools([_tool("alpha")])
    observation = validate_hosted_response(
        _response(_function("finish")), catalogue=catalogue,
    )
    assert observation.executable_deferred_names == ()
    assert observation.newly_loaded_names == ()
