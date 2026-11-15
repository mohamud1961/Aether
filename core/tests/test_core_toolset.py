"""Tool-screen arm T0 removes typed file operations. CLM history recall remains available."""

import pytest

from aether.core import harbor_config
from aether.core.tools import FILE_TOOLS_LINE, system_prompt, tools


def names(ts):
    return [t["function"]["name"] for t in ts]


def test_minimal_offers_terminal_and_finish_only():
    assert names(tools(python=False, file_tools=False)) == ["terminal", "finish"]
    assert names(tools(python=False, file_tools=False, terminal_events=True)) == ["terminal", "terminal_wait", "finish"]


def test_default_toolset_is_unchanged():
    assert names(tools(python=True)) == ["terminal", "python", "read_file", "write_file", "edit_file", "finish"]
    assert FILE_TOOLS_LINE in system_prompt(python_version="", clm=True)


def test_minimal_prompt_never_mentions_file_tools():
    text = system_prompt(python_version="", clm=True, file_tools=False)
    assert "read_file" not in text and "write_file" not in text and "edit_file" not in text


def test_the_switch_is_explicit(monkeypatch):
    for k, v in (("AETHER_CORE_REVIEW", "off"), ("AETHER_CORE_CONTEXT", "clm"), ("AETHER_CORE_REPL", "off"),
                 ("AETHER_CORE_IMAGES", "off")):
        monkeypatch.setenv(k, v)
    assert harbor_config.build_config().toolset == "full"
    monkeypatch.setenv("AETHER_CORE_TOOLSET", "minimal")
    assert harbor_config.build_config().toolset == "minimal"
    monkeypatch.setenv("AETHER_CORE_TOOLSET", "tiny")
    with pytest.raises(harbor_config.ConfigError):
        harbor_config.build_config()
