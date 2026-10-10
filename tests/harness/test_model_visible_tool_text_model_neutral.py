"""Model-visible tool schemas must not name a specific model (GLM is primary)."""
import json

from aether.persistent_provider_protocol import persistent_chat_provider_tools


def _all_tool_surfaces():
    import inspect
    params = inspect.signature(persistent_chat_provider_tools).parameters
    yield persistent_chat_provider_tools(**{k: v.default for k, v in params.items()
                                     if v.default is not inspect.Parameter.empty})


def test_chat_tool_schema_does_not_name_frontier():
    for tools in _all_tool_surfaces():
        text = json.dumps(tools)
        assert "Frontier" not in text, "model-visible tool text names a specific model"
