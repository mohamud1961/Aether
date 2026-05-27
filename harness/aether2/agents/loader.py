"""Agent loader adapted from a quarantined external TypeScript source tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping
import json
import re

from harness.aether2.skills.loader import (
    SkillHookCommand,
    SkillHookMatcher,
    SkillHookMetadata,
    parse_frontmatter_document,
)
from harness.aether2.tools.mcp import McpServerConfig


AgentSource = Literal["built-in", "flagSettings", "plugin", "policySettings", "projectSettings", "userSettings"]
AgentLoadedFrom = Literal["agents", "built-in", "plugin"]
AgentIsolation = Literal["worktree", "remote"]
AgentMemoryScope = Literal["local", "project", "user"]

_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off"}
_SUPPORTED_HOOK_EVENTS = {"PermissionRequest", "PostToolUse", "PreToolUse", "permission_request", "post_tool_use", "pre_tool_use"}
_HOOK_EVENT_ALIASES = {
    "PermissionRequest": "permission_request",
    "PostToolUse": "post_tool_use",
    "PreToolUse": "pre_tool_use",
    "permission_request": "permission_request",
    "post_tool_use": "post_tool_use",
    "pre_tool_use": "pre_tool_use",
}
_KNOWN_MCP_TRANSPORTS = {"fake_local", "http", "sdk", "sse", "stdio"}
_KNOWN_MCP_SCOPES = {"dynamic", "enterprise", "local", "managed", "project", "user"}
_KNOWN_MEMORY_SCOPES = {"local", "project", "user"}
_KNOWN_ISOLATION_MODES = {"remote", "worktree"}


@dataclass(frozen=True)
class AgentLoadIssue:
    reason_code: str
    message: str
    agent_type: str | None = None
    file_path: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "message": self.message,
            "agent_type": self.agent_type,
            "file_path": self.file_path,
            "source": self.source,
            "metadata": json.loads(json.dumps(self.metadata, sort_keys=True, ensure_ascii=True)),
        }


@dataclass(frozen=True)
class AgentMcpServerRef:
    name: str

    def as_dict(self) -> dict[str, Any]:
        return {"kind": "reference", "name": self.name}


@dataclass(frozen=True)
class AgentInlineMcpServer:
    name: str
    config: McpServerConfig

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "inline",
            "name": self.name,
            "config": {
                "type": self.config.type,
                "scope": self.config.scope,
                "command": self.config.command,
                "args": list(self.config.args),
                "url": self.config.url,
                "env": dict(self.config.env),
                "headers": dict(self.config.headers),
                "timeout_sec": self.config.timeout_sec,
            },
        }


AgentMcpServerSpec = AgentMcpServerRef | AgentInlineMcpServer


@dataclass(frozen=True)
class ParsedAgentFrontmatter:
    agent_type: str | None
    when_to_use: str | None
    tools: tuple[str, ...]
    disallowed_tools: tuple[str, ...]
    skills: tuple[str, ...]
    mcp_servers: tuple[AgentMcpServerSpec, ...]
    required_mcp_servers: tuple[str, ...]
    hooks: SkillHookMetadata
    color: str | None
    model: str | None
    effort: str | int | None
    permission_mode: str | None
    max_turns: int | None
    background: bool
    initial_prompt: str | None
    memory: AgentMemoryScope | None
    isolation: AgentIsolation | None
    critical_system_reminder: str | None
    omit_claude_md: bool
    issues: tuple[AgentLoadIssue, ...] = ()


@dataclass(frozen=True)
class AgentDefinition:
    agent_type: str
    when_to_use: str
    prompt: str
    source: AgentSource
    loaded_from: AgentLoadedFrom
    base_dir: str | None = None
    file_path: str | None = None
    canonical_file_path: str | None = None
    filename: str | None = None
    tools: tuple[str, ...] = ()
    disallowed_tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    mcp_servers: tuple[AgentMcpServerSpec, ...] = ()
    required_mcp_servers: tuple[str, ...] = ()
    hooks: SkillHookMetadata = field(default_factory=SkillHookMetadata)
    color: str | None = None
    model: str | None = None
    effort: str | int | None = None
    permission_mode: str | None = None
    max_turns: int | None = None
    background: bool = False
    initial_prompt: str | None = None
    memory: AgentMemoryScope | None = None
    isolation: AgentIsolation | None = None
    critical_system_reminder: str | None = None
    omit_claude_md: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "when_to_use": self.when_to_use,
            "prompt": self.prompt,
            "source": self.source,
            "loaded_from": self.loaded_from,
            "base_dir": self.base_dir,
            "file_path": self.file_path,
            "canonical_file_path": self.canonical_file_path,
            "filename": self.filename,
            "tools": list(self.tools),
            "disallowed_tools": list(self.disallowed_tools),
            "skills": list(self.skills),
            "mcp_servers": [spec.as_dict() for spec in self.mcp_servers],
            "required_mcp_servers": list(self.required_mcp_servers),
            "hooks": self.hooks.as_dict(),
            "color": self.color,
            "model": self.model,
            "effort": self.effort,
            "permission_mode": self.permission_mode,
            "max_turns": self.max_turns,
            "background": self.background,
            "initial_prompt": self.initial_prompt,
            "memory": self.memory,
            "isolation": self.isolation,
            "critical_system_reminder": self.critical_system_reminder,
            "omit_claude_md": self.omit_claude_md,
            "metadata": json.loads(json.dumps(self.metadata, sort_keys=True, ensure_ascii=True)),
        }


@dataclass(frozen=True)
class AgentLoadResult:
    agents: tuple[AgentDefinition, ...] = ()
    issues: tuple[AgentLoadIssue, ...] = ()


def parse_agent_frontmatter_fields(
    frontmatter: Mapping[str, Any],
    markdown_content: str,
    file_path: str,
    *,
    source: AgentSource,
) -> ParsedAgentFrontmatter:
    del markdown_content
    issues: list[AgentLoadIssue] = []
    agent_type = _coerce_optional_string(frontmatter.get("name"))
    if frontmatter.get("name") is not None and agent_type is None:
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_name",
                message="Agent name must be a non-empty string",
                file_path=file_path,
                source=source,
            )
        )
    description_value = frontmatter.get("description")
    when_to_use: str | None = None
    if description_value is not None:
        if isinstance(description_value, str) and description_value.strip():
            when_to_use = description_value.replace("\\n", "\n").strip()
        else:
            issues.append(
                AgentLoadIssue(
                    reason_code="invalid_agent_description",
                    message="Agent description must be a non-empty string",
                    agent_type=agent_type,
                    file_path=file_path,
                    source=source,
                )
            )

    mcp_servers, mcp_issues = _parse_mcp_servers(frontmatter.get("mcpServers"), agent_type, file_path, source)
    issues.extend(mcp_issues)
    hooks, hook_issues = _parse_hooks_from_frontmatter(frontmatter.get("hooks"), agent_type, file_path, source)
    issues.extend(hook_issues)

    max_turns = _parse_positive_int(frontmatter.get("maxTurns"))
    if frontmatter.get("maxTurns") is not None and max_turns is None:
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_max_turns",
                message="maxTurns must be a positive integer",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        )

    effort = frontmatter.get("effort")
    if effort is not None and not isinstance(effort, (int, str)):
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_effort",
                message="effort must be a string or integer",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        )
        effort = None

    memory = _coerce_optional_string(frontmatter.get("memory"))
    if memory is not None and memory not in _KNOWN_MEMORY_SCOPES:
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_memory",
                message=f"memory must be one of {sorted(_KNOWN_MEMORY_SCOPES)}",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        )
        memory = None

    isolation = _coerce_optional_string(frontmatter.get("isolation"))
    if isolation is not None and isolation not in _KNOWN_ISOLATION_MODES:
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_isolation",
                message=f"isolation must be one of {sorted(_KNOWN_ISOLATION_MODES)}",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        )
        isolation = None

    return ParsedAgentFrontmatter(
        agent_type=agent_type,
        when_to_use=when_to_use,
        tools=tuple(_parse_string_list(frontmatter.get("tools"), delimiter=",")),
        disallowed_tools=tuple(_parse_string_list(frontmatter.get("disallowedTools"), delimiter=",")),
        skills=tuple(_parse_string_list(frontmatter.get("skills"), delimiter=",")),
        mcp_servers=tuple(mcp_servers),
        required_mcp_servers=tuple(_parse_string_list(frontmatter.get("requiredMcpServers"), delimiter=",")),
        hooks=hooks,
        color=_coerce_optional_string(frontmatter.get("color")),
        model=_coerce_model(frontmatter.get("model")),
        effort=effort,
        permission_mode=_coerce_optional_string(frontmatter.get("permissionMode")),
        max_turns=max_turns,
        background=_parse_bool(frontmatter.get("background"), default=False),
        initial_prompt=_coerce_optional_string(frontmatter.get("initialPrompt")),
        memory=memory,  # type: ignore[arg-type]
        isolation=isolation,  # type: ignore[arg-type]
        critical_system_reminder=_coerce_optional_string(frontmatter.get("criticalSystemReminder_EXPERIMENTAL")),
        omit_claude_md=_parse_bool(frontmatter.get("omitClaudeMd"), default=False),
        issues=tuple(issues),
    )


def create_agent_definition(
    *,
    agent_type: str,
    when_to_use: str,
    markdown_content: str,
    source: AgentSource,
    loaded_from: AgentLoadedFrom,
    base_dir: str | None,
    file_path: str | None,
    tools: Iterable[str],
    disallowed_tools: Iterable[str],
    skills: Iterable[str],
    mcp_servers: Iterable[AgentMcpServerSpec],
    required_mcp_servers: Iterable[str],
    hooks: SkillHookMetadata,
    color: str | None,
    model: str | None,
    effort: str | int | None,
    permission_mode: str | None,
    max_turns: int | None,
    background: bool,
    initial_prompt: str | None,
    memory: AgentMemoryScope | None,
    isolation: AgentIsolation | None,
    critical_system_reminder: str | None,
    omit_claude_md: bool,
    metadata: Mapping[str, Any] | None = None,
) -> AgentDefinition:
    canonical_path: str | None = None
    filename: str | None = None
    if file_path is not None:
        filename = Path(file_path).stem
        try:
            canonical_path = str(Path(file_path).resolve(strict=True))
        except FileNotFoundError:
            canonical_path = None
    base_metadata = {
        "content_length": len(markdown_content),
        "has_mcp_refs": bool(tuple(mcp_servers)),
        "has_skill_refs": bool(tuple(skills)),
        "retains_hooks": hooks.has_supported_hooks,
        "retains_permission_mode": permission_mode is not None,
    }
    if metadata:
        base_metadata.update(json.loads(json.dumps(dict(metadata), sort_keys=True, ensure_ascii=True)))
    return AgentDefinition(
        agent_type=agent_type,
        when_to_use=when_to_use,
        prompt=markdown_content.strip(),
        source=source,
        loaded_from=loaded_from,
        base_dir=base_dir,
        file_path=file_path,
        canonical_file_path=canonical_path,
        filename=filename,
        tools=tuple(tools),
        disallowed_tools=tuple(disallowed_tools),
        skills=tuple(skills),
        mcp_servers=tuple(mcp_servers),
        required_mcp_servers=tuple(required_mcp_servers),
        hooks=hooks,
        color=color,
        model=model,
        effort=effort,
        permission_mode=permission_mode,
        max_turns=max_turns,
        background=background,
        initial_prompt=initial_prompt,
        memory=memory,
        isolation=isolation,
        critical_system_reminder=critical_system_reminder,
        omit_claude_md=omit_claude_md,
        metadata=base_metadata,
    )


def load_agents_from_directory(base_path: str | Path, source: AgentSource) -> AgentLoadResult:
    base_dir = Path(base_path)
    if not base_dir.exists():
        return AgentLoadResult(
            issues=(
                AgentLoadIssue(
                    reason_code="agents_directory_missing",
                    message="agents directory does not exist",
                    file_path=str(base_dir),
                    source=source,
                ),
            )
        )
    if not base_dir.is_dir():
        return AgentLoadResult(
            issues=(
                AgentLoadIssue(
                    reason_code="agents_directory_invalid",
                    message="agents base path is not a directory",
                    file_path=str(base_dir),
                    source=source,
                ),
            )
        )

    agents: list[AgentDefinition] = []
    issues: list[AgentLoadIssue] = []
    for entry in sorted(base_dir.iterdir(), key=lambda item: item.name):
        if not entry.is_file() or entry.suffix.lower() != ".md":
            continue
        try:
            raw_text = entry.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(
                AgentLoadIssue(
                    reason_code="agent_read_failed",
                    message=f"Failed to read agent file: {exc}",
                    file_path=str(entry),
                    source=source,
                )
            )
            continue
        frontmatter, content, parse_issues = parse_frontmatter_document(raw_text, str(entry))
        issues.extend(
            AgentLoadIssue(
                reason_code=issue.reason_code,
                message=issue.message,
                file_path=issue.file_path,
                source=source,
                metadata=dict(issue.metadata),
            )
            for issue in parse_issues
        )
        parsed = parse_agent_frontmatter_fields(frontmatter, content, str(entry), source=source)
        issues.extend(parsed.issues)
        if parsed.agent_type is None:
            continue
        if parsed.when_to_use is None:
            issues.append(
                AgentLoadIssue(
                    reason_code="agent_description_missing",
                    message="Agent frontmatter requires a description field",
                    agent_type=parsed.agent_type,
                    file_path=str(entry),
                    source=source,
                )
            )
            continue
        agents.append(
            create_agent_definition(
                agent_type=parsed.agent_type,
                when_to_use=parsed.when_to_use,
                markdown_content=content,
                source=source,
                loaded_from="agents",
                base_dir=str(base_dir.resolve()),
                file_path=str(entry),
                tools=parsed.tools,
                disallowed_tools=parsed.disallowed_tools,
                skills=parsed.skills,
                mcp_servers=parsed.mcp_servers,
                required_mcp_servers=parsed.required_mcp_servers,
                hooks=parsed.hooks,
                color=parsed.color,
                model=parsed.model,
                effort=parsed.effort,
                permission_mode=parsed.permission_mode,
                max_turns=parsed.max_turns,
                background=parsed.background,
                initial_prompt=parsed.initial_prompt,
                memory=parsed.memory,
                isolation=parsed.isolation,
                critical_system_reminder=parsed.critical_system_reminder,
                omit_claude_md=parsed.omit_claude_md,
            )
        )
    return AgentLoadResult(agents=tuple(agents), issues=tuple(issues))


def get_active_agents_from_list(all_agents: Iterable[AgentDefinition]) -> list[AgentDefinition]:
    groups = {
        "built-in": [],
        "plugin": [],
        "userSettings": [],
        "projectSettings": [],
        "flagSettings": [],
        "policySettings": [],
    }
    for agent in all_agents:
        groups.setdefault(agent.source, []).append(agent)
    winners: dict[str, AgentDefinition] = {}
    for source_name in ("built-in", "plugin", "userSettings", "projectSettings", "flagSettings", "policySettings"):
        for agent in groups.get(source_name, ()):
            winners[agent.agent_type] = agent
    return list(winners.values())


def has_required_mcp_servers(agent: AgentDefinition, available_servers: Iterable[str]) -> bool:
    available = tuple(available_servers)
    if not agent.required_mcp_servers:
        return True
    return all(any(pattern.casefold() in server.casefold() for server in available) for pattern in agent.required_mcp_servers)


def filter_agents_by_mcp_requirements(
    agents: Iterable[AgentDefinition],
    available_servers: Iterable[str],
) -> list[AgentDefinition]:
    available = tuple(available_servers)
    return [agent for agent in agents if has_required_mcp_servers(agent, available)]


def _parse_mcp_servers(
    value: Any,
    agent_type: str | None,
    file_path: str,
    source: AgentSource,
) -> tuple[list[AgentMcpServerSpec], list[AgentLoadIssue]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], [
            AgentLoadIssue(
                reason_code="invalid_agent_mcp_servers",
                message="mcpServers must be a list of server references or inline definitions",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        ]
    specs: list[AgentMcpServerSpec] = []
    issues: list[AgentLoadIssue] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            name = item.strip()
            if name:
                specs.append(AgentMcpServerRef(name=name))
                continue
        elif isinstance(item, Mapping) and len(item) == 1:
            name, config_payload = next(iter(item.items()))
            if isinstance(name, str) and name.strip() and isinstance(config_payload, Mapping):
                config = _coerce_mcp_config(config_payload)
                if config is None:
                    issues.append(
                        AgentLoadIssue(
                            reason_code="invalid_agent_mcp_server_config",
                            message=f"mcpServers[{index}] inline config is invalid",
                            agent_type=agent_type,
                            file_path=file_path,
                            source=source,
                            metadata={"server_name": name},
                        )
                    )
                else:
                    specs.append(AgentInlineMcpServer(name=name, config=config))
                continue
        issues.append(
            AgentLoadIssue(
                reason_code="invalid_agent_mcp_servers",
                message=f"mcpServers[{index}] must be a server name or a single-entry mapping",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            )
        )
    return specs, issues


def _coerce_mcp_config(value: Mapping[str, Any]) -> McpServerConfig | None:
    transport = _coerce_optional_string(value.get("type"))
    if transport is None or transport not in _KNOWN_MCP_TRANSPORTS:
        return None
    scope = _coerce_optional_string(value.get("scope")) or "dynamic"
    if scope not in _KNOWN_MCP_SCOPES:
        scope = "dynamic"
    args = tuple(_parse_string_list(value.get("args"), delimiter=","))
    env = _coerce_string_mapping(value.get("env"))
    headers = _coerce_string_mapping(value.get("headers"))
    timeout_sec = _coerce_timeout(value.get("timeout_sec"))
    return McpServerConfig(
        type=transport,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        command=_coerce_optional_string(value.get("command")),
        args=args,
        url=_coerce_optional_string(value.get("url")),
        env=env,
        headers=headers,
        timeout_sec=timeout_sec,
    )


def _coerce_timeout(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def _coerce_string_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key] = item
    return result


def _parse_hooks_from_frontmatter(
    value: Any,
    agent_type: str | None,
    file_path: str,
    source: AgentSource,
) -> tuple[SkillHookMetadata, tuple[AgentLoadIssue, ...]]:
    if value is None:
        return SkillHookMetadata(), ()
    if not isinstance(value, Mapping):
        return SkillHookMetadata(), (
            AgentLoadIssue(
                reason_code="invalid_agent_hooks_metadata",
                message="hooks frontmatter must be a mapping",
                agent_type=agent_type,
                file_path=file_path,
                source=source,
            ),
        )
    issues: list[AgentLoadIssue] = []
    matchers: list[SkillHookMatcher] = []
    unsupported_events: list[str] = []
    for event_name in sorted(value):
        normalized_event = _HOOK_EVENT_ALIASES.get(str(event_name))
        if normalized_event is None:
            unsupported_events.append(str(event_name))
            issues.append(
                AgentLoadIssue(
                    reason_code="unsupported_agent_hook_event",
                    message=f"Unsupported agent hook event '{event_name}' for the current Aether hook substrate",
                    agent_type=agent_type,
                    file_path=file_path,
                    source=source,
                    metadata={"supported_events": sorted(_SUPPORTED_HOOK_EVENTS)},
                )
            )
        raw_matchers = value[event_name]
        if not isinstance(raw_matchers, list):
            issues.append(
                AgentLoadIssue(
                    reason_code="invalid_agent_hooks_metadata",
                    message=f"hooks.{event_name} must be a list of matcher entries",
                    agent_type=agent_type,
                    file_path=file_path,
                    source=source,
                )
            )
            continue
        for index, raw_matcher in enumerate(raw_matchers):
            if not isinstance(raw_matcher, Mapping):
                issues.append(
                    AgentLoadIssue(
                        reason_code="invalid_agent_hooks_metadata",
                        message=f"hooks.{event_name}[{index}] must be a mapping",
                        agent_type=agent_type,
                        file_path=file_path,
                        source=source,
                    )
                )
                continue
            matcher_text = _coerce_optional_string(raw_matcher.get("matcher")) or ""
            raw_hooks = raw_matcher.get("hooks")
            if not isinstance(raw_hooks, list) or not raw_hooks:
                issues.append(
                    AgentLoadIssue(
                        reason_code="invalid_agent_hooks_metadata",
                        message=f"hooks.{event_name}[{index}].hooks must be a non-empty list",
                        agent_type=agent_type,
                        file_path=file_path,
                        source=source,
                    )
                )
                continue
            hook_commands: list[SkillHookCommand] = []
            for raw_hook in raw_hooks:
                if isinstance(raw_hook, str):
                    hook_commands.append(SkillHookCommand(raw=raw_hook))
                    continue
                if isinstance(raw_hook, Mapping):
                    hook_commands.append(
                        SkillHookCommand(
                            raw=json.loads(json.dumps(dict(raw_hook), sort_keys=True, ensure_ascii=True)),
                            once=_parse_bool(raw_hook.get("once"), default=False),
                        )
                    )
                    continue
                issues.append(
                    AgentLoadIssue(
                        reason_code="invalid_agent_hooks_metadata",
                        message=f"hooks.{event_name}[{index}].hooks entries must be strings or mappings",
                        agent_type=agent_type,
                        file_path=file_path,
                        source=source,
                    )
                )
            if hook_commands:
                matchers.append(
                    SkillHookMatcher(
                        original_event=str(event_name),
                        normalized_event=normalized_event,  # type: ignore[arg-type]
                        matcher=matcher_text,
                        hooks=tuple(hook_commands),
                    )
                )
    return SkillHookMetadata(matchers=tuple(matchers), unsupported_events=tuple(unsupported_events)), tuple(issues)


def _parse_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            return True
        if normalized in _FALSE_STRINGS:
            return False
    return default


def _parse_string_list(value: Any, *, delimiter: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [part.strip() for chunk in value.splitlines() for part in chunk.split(delimiter)]
        return [part for part in parts if part]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    items.append(stripped)
        return items
    return []


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _coerce_model(value: Any) -> str | None:
    model = _coerce_optional_string(value)
    if model is None:
        return None
    return None if model.casefold() == "inherit" else model


def _parse_positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


__all__ = [
    "AgentDefinition",
    "AgentInlineMcpServer",
    "AgentIsolation",
    "AgentLoadIssue",
    "AgentLoadResult",
    "AgentLoadedFrom",
    "AgentMcpServerRef",
    "AgentMcpServerSpec",
    "AgentMemoryScope",
    "AgentSource",
    "ParsedAgentFrontmatter",
    "create_agent_definition",
    "filter_agents_by_mcp_requirements",
    "get_active_agents_from_list",
    "has_required_mcp_servers",
    "load_agents_from_directory",
    "parse_agent_frontmatter_fields",
]
