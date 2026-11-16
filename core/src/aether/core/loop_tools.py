"""The tool list a run offers the model (split from loop.py, module cap).

``toolset`` "python" (B18, AETHER_CORE_TOOLSET=python) offers only the persistent REPL and finish; terminal work,
files and the task's MCP servers are library functions inside the REPL (repl_lib_src). Off by default.
"""

from __future__ import annotations

from typing import Any

from . import browser, image_region, images, intent, open_issues, runstate
from .loop_config import VERIFIER_ROLE
from .tools import tools


def assemble(s: Any, config: Any, python: str) -> bool:
    """Set ``s.tools`` for this run; returns whether images can be viewed."""
    see = config.images and images.available()
    python_only = config.toolset == "python"
    s.tools = tools(
        python=bool(python),
        images=see,
        history=config.context == "clm",
        verdict=config.role == VERIFIER_ROLE,
        terminal_events=config.terminal_events and config.role == "worker",
        file_tools=config.toolset == "full",
        python_only=python_only,
    )
    if python_only and not python:
        raise RuntimeError("toolset=python needs a working python3 in the task environment")
    if getattr(config, "mcp_servers", ()) and config.role == "worker":
        from . import mcp

        s.mcp = mcp.Mcp(s.env, config.control_dir, list(config.mcp_servers), adopt=config.terminal_events,
                        idempotency=config.mcp_idempotency, fast_wait=config.fast_mcp_wait)
        if config.terminal_events:
            s.mcp.conversation, s.mcp.delivery_tag = s.terminals.conversation, s.delivery_tag
        if python_only:  # the REPL's mcp() asks the host to start a server's client; the calls stay in the sandbox
            s.repl.mcp = s.mcp
        else:
            s.tools = [*s.tools, mcp.tool(list(config.mcp_servers))]
    if config.workspace_search and config.role == "worker":
        from . import workspace_search

        s.tools.append(workspace_search.TOOL)
    if config.evidence_presentation == "path_lookup" and config.role == "worker":
        from .evidence_context import LOCATE_TOOL

        s.tools.append(LOCATE_TOOL)
    if see and config.context == "clm" and config.clm.attest_original_history:
        s.tools = images.with_history_recall(s.tools)
    if config.image_region and see:
        s.tools = image_region.with_region(s.tools)
    if config.image_compare and see:
        s.tools = image_region.with_compare(s.tools)
    if config.intent:
        s.tools = intent.with_intent(s.tools)
    if config.open_issues:
        s.tools = open_issues.with_field(s.tools)
    s.tools = browser.with_tool(s.tools, config.browser_session) if config.browser else s.tools
    if s.state:
        s.tools = runstate.with_state(s.tools)
    return see
