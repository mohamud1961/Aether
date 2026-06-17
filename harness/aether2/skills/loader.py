"""Owned Python skill loader for the Aether runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping
import ast
import json
import re

from harness.aether2.skills.registry import MCPSkillBuilders, register_mcp_skill_builders


LoadedFrom = Literal["skills", "bundled", "mcp", "plugin", "managed", "commands_DEPRECATED"]
SkillExecutionContext = Literal["inline", "fork"]
SkillSource = Literal["policySettings", "userSettings", "projectSettings", "plugin", "bundled", "mcp"]
SkillHookEvent = Literal["permission_request", "pre_tool_use", "post_tool_use"]

_FRONTMATTER_BOUNDARY = "---"
_HOOK_EVENT_ALIASES = {
    "PermissionRequest": "permission_request",
    "PreToolUse": "pre_tool_use",
    "PostToolUse": "post_tool_use",
    "permission_request": "permission_request",
    "pre_tool_use": "pre_tool_use",
    "post_tool_use": "post_tool_use",
}
_SUPPORTED_HOOK_EVENTS = tuple(_HOOK_EVENT_ALIASES)
_TRUE_STRINGS = {"1", "true", "yes", "on"}
_FALSE_STRINGS = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class SkillLoadIssue:
    reason_code: str
    message: str
    skill_name: str | None = None
    file_path: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "message": self.message,
            "skill_name": self.skill_name,
            "file_path": self.file_path,
            "source": self.source,
            "metadata": json.loads(json.dumps(self.metadata, sort_keys=True, ensure_ascii=True)),
        }


@dataclass(frozen=True)
class SkillHookCommand:
    raw: str | dict[str, Any]
    once: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"once": self.once}
        if isinstance(self.raw, str):
            payload["command"] = self.raw
        else:
            payload["command"] = json.loads(json.dumps(self.raw, sort_keys=True, ensure_ascii=True))
        return payload


@dataclass(frozen=True)
class SkillHookMatcher:
    original_event: str
    normalized_event: SkillHookEvent | None
    matcher: str
    hooks: tuple[SkillHookCommand, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_event": self.original_event,
            "normalized_event": self.normalized_event,
            "matcher": self.matcher,
            "hooks": [hook.as_dict() for hook in self.hooks],
        }


@dataclass(frozen=True)
class SkillHookMetadata:
    matchers: tuple[SkillHookMatcher, ...] = ()
    unsupported_events: tuple[str, ...] = ()

    @property
    def has_supported_hooks(self) -> bool:
        return any(matcher.normalized_event is not None and matcher.hooks for matcher in self.matchers)

    def as_dict(self) -> dict[str, Any]:
        return {
            "matchers": [matcher.as_dict() for matcher in self.matchers],
            "unsupported_events": list(self.unsupported_events),
        }


@dataclass(frozen=True)
class ParsedSkillFrontmatter:
    display_name: str | None
    description: str
    has_user_specified_description: bool
    allowed_tools: tuple[str, ...]
    argument_hint: str | None
    argument_names: tuple[str, ...]
    when_to_use: str | None
    version: str | None
    model: str | None
    disable_model_invocation: bool
    user_invocable: bool
    hooks: SkillHookMetadata
    execution_context: SkillExecutionContext | None
    agent: str | None
    effort: str | int | None
    shell: str | dict[str, Any] | None
    paths: tuple[str, ...] | None
    issues: tuple[SkillLoadIssue, ...] = ()


@dataclass(frozen=True)
class SkillSpec:
    name: str
    description: str
    content: str
    source: SkillSource
    loaded_from: LoadedFrom
    skill_root: str | None = None
    file_path: str | None = None
    canonical_file_path: str | None = None
    display_name: str | None = None
    when_to_use: str | None = None
    version: str | None = None
    model: str | None = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    allowed_tools: tuple[str, ...] = ()
    argument_hint: str | None = None
    argument_names: tuple[str, ...] = ()
    hooks: SkillHookMetadata = field(default_factory=SkillHookMetadata)
    execution_context: SkillExecutionContext | None = None
    agent: str | None = None
    effort: str | int | None = None
    shell: str | dict[str, Any] | None = None
    paths: tuple[str, ...] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_hidden(self) -> bool:
        return not self.user_invocable

    @property
    def content_length(self) -> int:
        return len(self.content)

    def user_facing_name(self) -> str:
        return self.display_name or self.name

    def rendered_text(self) -> str:
        if not self.skill_root:
            return self.content
        return f"Base directory for this skill: {self.skill_root}\n\n{self.content}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "source": self.source,
            "loaded_from": self.loaded_from,
            "skill_root": self.skill_root,
            "file_path": self.file_path,
            "canonical_file_path": self.canonical_file_path,
            "when_to_use": self.when_to_use,
            "version": self.version,
            "model": self.model,
            "disable_model_invocation": self.disable_model_invocation,
            "user_invocable": self.user_invocable,
            "allowed_tools": list(self.allowed_tools),
            "argument_hint": self.argument_hint,
            "argument_names": list(self.argument_names),
            "hooks": self.hooks.as_dict(),
            "execution_context": self.execution_context,
            "agent": self.agent,
            "effort": self.effort,
            "shell": self.shell,
            "paths": list(self.paths) if self.paths is not None else None,
            "metadata": json.loads(json.dumps(self.metadata, sort_keys=True, ensure_ascii=True)),
        }


@dataclass(frozen=True)
class SkillLoadResult:
    skills: tuple[SkillSpec, ...] = ()
    issues: tuple[SkillLoadIssue, ...] = ()


def estimate_skill_frontmatter_tokens(skill: SkillSpec) -> int:
    frontmatter_text = " ".join(
        part for part in (skill.name, skill.description, skill.when_to_use or "") if part
    )
    return max(1, len(frontmatter_text) // 4) if frontmatter_text else 0


def parse_frontmatter_document(text: str, file_path: str) -> tuple[dict[str, Any], str, tuple[SkillLoadIssue, ...]]:
    if not text.startswith(f"{_FRONTMATTER_BOUNDARY}\n"):
        return {}, text, ()
    lines = text.splitlines()
    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_BOUNDARY:
            closing_index = index
            break
    if closing_index is None:
        return {}, text, (
            SkillLoadIssue(
                reason_code="invalid_frontmatter",
                message="Frontmatter starts with '---' but has no closing delimiter",
                file_path=file_path,
            ),
        )
    raw_frontmatter = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).lstrip("\n")
    try:
        parsed = _parse_simple_yaml(raw_frontmatter) if raw_frontmatter.strip() else {}
    except ValueError as exc:
        return {}, body, (
            SkillLoadIssue(
                reason_code="invalid_frontmatter",
                message=f"Failed to parse YAML frontmatter: {exc}",
                file_path=file_path,
            ),
        )
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, Mapping):
        return {}, body, (
            SkillLoadIssue(
                reason_code="invalid_frontmatter",
                message="Skill frontmatter must parse to a mapping",
                file_path=file_path,
            ),
        )
    return dict(parsed), body, ()


def parse_skill_frontmatter_fields(
    frontmatter: Mapping[str, Any],
    markdown_content: str,
    resolved_name: str,
    description_fallback_label: str = "Skill",
) -> ParsedSkillFrontmatter:
    issues: list[SkillLoadIssue] = []
    description_value = frontmatter.get("description")
    user_description: str | None = None
    if description_value is not None:
        if isinstance(description_value, str):
            user_description = description_value.strip()
        else:
            issues.append(
                SkillLoadIssue(
                    reason_code="invalid_description_frontmatter",
                    message="description frontmatter must be a string",
                    skill_name=resolved_name,
                )
            )
    description = user_description or _extract_description_from_markdown(markdown_content, description_fallback_label)

    hooks, hook_issues = _parse_hooks_from_frontmatter(frontmatter.get("hooks"), resolved_name)
    issues.extend(hook_issues)

    effort = frontmatter.get("effort")
    if effort is not None and not isinstance(effort, (str, int)):
        issues.append(
            SkillLoadIssue(
                reason_code="invalid_effort_frontmatter",
                message="effort frontmatter must be a string or integer",
                skill_name=resolved_name,
            )
        )
        effort = None

    execution_context = "fork" if frontmatter.get("context") == "fork" else None
    shell_value = frontmatter.get("shell")
    if shell_value is not None and not isinstance(shell_value, (str, Mapping)):
        issues.append(
            SkillLoadIssue(
                reason_code="invalid_shell_frontmatter",
                message="shell frontmatter must be a string or mapping",
                skill_name=resolved_name,
            )
        )
        shell_value = None

    return ParsedSkillFrontmatter(
        display_name=_coerce_optional_string(frontmatter.get("name")),
        description=description,
        has_user_specified_description=user_description is not None,
        allowed_tools=tuple(_parse_string_list(frontmatter.get("allowed-tools"), delimiter=",")),
        argument_hint=_coerce_optional_string(frontmatter.get("argument-hint")),
        argument_names=tuple(_parse_argument_names(frontmatter.get("arguments"))),
        when_to_use=_coerce_optional_string(frontmatter.get("when_to_use")),
        version=_coerce_optional_string(frontmatter.get("version")),
        model=_coerce_model(frontmatter.get("model")),
        disable_model_invocation=_parse_bool(frontmatter.get("disable-model-invocation"), default=False),
        user_invocable=_parse_bool(frontmatter.get("user-invocable"), default=True),
        hooks=hooks,
        execution_context=execution_context,
        agent=_coerce_optional_string(frontmatter.get("agent")),
        effort=effort,
        shell=json.loads(json.dumps(shell_value, sort_keys=True, ensure_ascii=True))
        if isinstance(shell_value, Mapping)
        else shell_value,
        paths=_parse_skill_paths(frontmatter.get("paths")),
        issues=tuple(issues),
    )


def create_skill_spec(
    *,
    skill_name: str,
    display_name: str | None,
    description: str,
    has_user_specified_description: bool,
    markdown_content: str,
    allowed_tools: Iterable[str],
    argument_hint: str | None,
    argument_names: Iterable[str],
    when_to_use: str | None,
    version: str | None,
    model: str | None,
    disable_model_invocation: bool,
    user_invocable: bool,
    source: SkillSource,
    base_dir: str | None,
    loaded_from: LoadedFrom,
    hooks: SkillHookMetadata,
    execution_context: SkillExecutionContext | None,
    agent: str | None,
    paths: tuple[str, ...] | None,
    effort: str | int | None,
    shell: str | dict[str, Any] | None,
    file_path: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> SkillSpec:
    canonical_path: str | None = None
    if file_path is not None:
        try:
            canonical_path = str(Path(file_path).resolve(strict=True))
        except FileNotFoundError:
            canonical_path = None
    base_metadata = {
        "has_user_specified_description": has_user_specified_description,
        "content_length": len(markdown_content),
    }
    if metadata:
        base_metadata.update(json.loads(json.dumps(dict(metadata), sort_keys=True, ensure_ascii=True)))
    return SkillSpec(
        name=skill_name,
        display_name=display_name,
        description=description,
        content=markdown_content,
        source=source,
        loaded_from=loaded_from,
        skill_root=base_dir,
        file_path=file_path,
        canonical_file_path=canonical_path,
        when_to_use=when_to_use,
        version=version,
        model=model,
        disable_model_invocation=disable_model_invocation,
        user_invocable=user_invocable,
        allowed_tools=tuple(allowed_tools),
        argument_hint=argument_hint,
        argument_names=tuple(argument_names),
        hooks=hooks,
        execution_context=execution_context,
        agent=agent,
        effort=effort,
        shell=shell,
        paths=paths,
        metadata=base_metadata,
    )


def load_skills_from_directory(base_path: str | Path, source: SkillSource) -> SkillLoadResult:
    base_dir = Path(base_path)
    if not base_dir.exists():
        return SkillLoadResult(
            issues=(
                SkillLoadIssue(
                    reason_code="skills_directory_missing",
                    message="skills directory does not exist",
                    file_path=str(base_dir),
                    source=source,
                ),
            )
        )
    if not base_dir.is_dir():
        return SkillLoadResult(
            issues=(
                SkillLoadIssue(
                    reason_code="skills_directory_invalid",
                    message="skills base path is not a directory",
                    file_path=str(base_dir),
                    source=source,
                ),
            )
        )

    skills: list[SkillSpec] = []
    issues: list[SkillLoadIssue] = []
    for entry in sorted(base_dir.iterdir(), key=lambda item: item.name):
        if not (entry.is_dir() or entry.is_symlink()):
            continue
        skill_file = entry / "SKILL.md"
        if not skill_file.exists():
            issues.append(
                SkillLoadIssue(
                    reason_code="skill_file_missing",
                    message="Skill directory does not contain SKILL.md",
                    skill_name=entry.name,
                    file_path=str(skill_file),
                    source=source,
                )
            )
            continue
        try:
            raw_text = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(
                SkillLoadIssue(
                    reason_code="skill_read_failed",
                    message=f"Failed to read skill file: {exc}",
                    skill_name=entry.name,
                    file_path=str(skill_file),
                    source=source,
                )
            )
            continue
        frontmatter, content, parse_issues = parse_frontmatter_document(raw_text, str(skill_file))
        issues.extend(parse_issues)
        parsed = parse_skill_frontmatter_fields(frontmatter, content, entry.name)
        issues.extend(parsed.issues)
        skills.append(
            create_skill_spec(
                skill_name=entry.name,
                display_name=parsed.display_name,
                description=parsed.description,
                has_user_specified_description=parsed.has_user_specified_description,
                markdown_content=content,
                allowed_tools=parsed.allowed_tools,
                argument_hint=parsed.argument_hint,
                argument_names=parsed.argument_names,
                when_to_use=parsed.when_to_use,
                version=parsed.version,
                model=parsed.model,
                disable_model_invocation=parsed.disable_model_invocation,
                user_invocable=parsed.user_invocable,
                source=source,
                base_dir=str(entry.resolve()),
                loaded_from="skills",
                hooks=parsed.hooks,
                execution_context=parsed.execution_context,
                agent=parsed.agent,
                paths=parsed.paths,
                effort=parsed.effort,
                shell=parsed.shell,
                file_path=str(skill_file),
            )
        )
    return SkillLoadResult(skills=tuple(skills), issues=tuple(issues))


def discover_skill_directories_for_paths(
    file_paths: Iterable[str | Path],
    cwd: str | Path,
    *,
    seen_dirs: Iterable[str | Path] | None = None,
) -> tuple[str, ...]:
    resolved_cwd = Path(cwd).resolve()
    seen = {str(Path(path).resolve()) for path in (seen_dirs or ())}
    discovered: set[str] = set()
    for file_path in file_paths:
        current_dir = Path(file_path).resolve().parent
        while current_dir != resolved_cwd and _is_within(current_dir, resolved_cwd):
            skill_dir = current_dir / ".claude" / "skills"
            skill_dir_key = str(skill_dir.resolve(strict=False))
            if skill_dir_key not in seen and skill_dir.is_dir():
                discovered.add(skill_dir_key)
                seen.add(skill_dir_key)
            parent = current_dir.parent
            if parent == current_dir:
                break
            current_dir = parent
    return tuple(sorted(discovered, key=lambda path: (-len(Path(path).parts), path)))


def skill_matches_paths(skill: SkillSpec, file_paths: Iterable[str | Path], cwd: str | Path) -> bool:
    if not skill.paths:
        return True
    resolved_cwd = Path(cwd).resolve()
    patterns = tuple(skill.paths)
    for file_path in file_paths:
        relative_path = _relative_posix_path(file_path, resolved_cwd)
        if relative_path is None:
            continue
        if any(_matches_pattern(relative_path, pattern) for pattern in patterns):
            return True
    return False


def _extract_description_from_markdown(markdown: str, fallback_label: str) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line.startswith("#"):
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    if paragraphs:
        return paragraphs[0]
    return f"{fallback_label} {fallback_label.lower()} content."


def _parse_simple_yaml(raw_frontmatter: str) -> dict[str, Any]:
    lines = raw_frontmatter.splitlines()
    payload, index = _parse_yaml_block(lines, 0, 0)
    if index < len(lines):
        trailing = next((line for line in lines[index:] if line.strip()), None)
        if trailing is not None:
            raise ValueError(f"unexpected trailing content: {trailing}")
    if not isinstance(payload, dict):
        raise ValueError("frontmatter root must be a mapping")
    return payload


def _parse_yaml_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    mapping: dict[str, Any] = {}
    sequence: list[Any] = []
    mode: str | None = None
    index = start
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        current_indent = len(raw_line) - len(raw_line.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"unexpected indentation at line: {raw_line.strip()}")
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if mode not in (None, "list"):
                raise ValueError("cannot mix mapping and list items at the same indentation level")
            mode = "list"
            item_text = stripped[2:].strip()
            index += 1
            item, index = _parse_list_item(item_text, lines, index, indent + 2)
            sequence.append(item)
            continue
        if mode not in (None, "map"):
            raise ValueError("cannot mix list and mapping items at the same indentation level")
        mode = "map"
        key, inline_value = _split_key_value(stripped)
        if key is None:
            raise ValueError(f"invalid mapping entry: {stripped}")
        index += 1
        if inline_value is None:
            nested, index = _parse_yaml_block(lines, index, indent + 2)
            mapping[key] = nested
        else:
            mapping[key] = _parse_scalar(inline_value)
    if mode == "list":
        return sequence, index
    return mapping, index


def _parse_list_item(item_text: str, lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    if not item_text:
        return _parse_yaml_block(lines, index, indent)
    key, inline_value = _split_key_value(item_text)
    if key is None:
        return _parse_scalar(item_text), index
    payload: dict[str, Any] = {}
    payload[key] = {} if inline_value is None else _parse_scalar(inline_value)
    while index < len(lines):
        raw_line = lines[index]
        if not raw_line.strip():
            index += 1
            continue
        current_indent = len(raw_line) - len(raw_line.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            if inline_value is not None:
                nested, index = _parse_yaml_block(lines, index, indent)
                if not isinstance(nested, dict):
                    raise ValueError("list-item continuation must be a mapping")
                payload.update(nested)
                continue
            nested, index = _parse_yaml_block(lines, index, indent + 2)
            payload[key] = nested
            continue
        next_key, next_inline = _split_key_value(raw_line.strip())
        if next_key is None:
            break
        index += 1
        if next_inline is None:
            nested, index = _parse_yaml_block(lines, index, indent + 2)
            payload[next_key] = nested
        else:
            payload[next_key] = _parse_scalar(next_inline)
    return payload, index


def _split_key_value(text: str) -> tuple[str | None, str | None]:
    if ":" not in text:
        return None, None
    key, remainder = text.split(":", 1)
    key = key.strip()
    if not key:
        return None, None
    remainder = remainder.lstrip()
    if not remainder:
        return key, None
    return key, remainder


def _parse_scalar(value: str) -> Any:
    if value in {"''", '""'}:
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith("[") and not value.endswith("]")) or (value.startswith("{") and not value.endswith("}")):
        raise ValueError(f"malformed scalar value: {value}")
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"malformed quoted scalar: {value}") from exc
    return value


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


def _parse_argument_names(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        tokens = re.split(r"[\s,]+", value.strip())
        return [token for token in tokens if token]
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    items.append(stripped)
        return items
    return []


def _parse_skill_paths(value: Any) -> tuple[str, ...] | None:
    patterns = _parse_string_list(value, delimiter=",")
    normalized = []
    for pattern in patterns:
        candidate = pattern.strip()
        if candidate.endswith("/**"):
            candidate = candidate[:-3]
        if candidate:
            normalized.append(candidate)
    if not normalized or all(pattern == "**" for pattern in normalized):
        return None
    return tuple(normalized)


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _coerce_model(value: Any) -> str | None:
    model = _coerce_optional_string(value)
    if model == "inherit":
        return None
    return model


def _parse_hooks_from_frontmatter(
    value: Any,
    resolved_name: str,
) -> tuple[SkillHookMetadata, tuple[SkillLoadIssue, ...]]:
    if value is None:
        return SkillHookMetadata(), ()
    if not isinstance(value, Mapping):
        return SkillHookMetadata(), (
            SkillLoadIssue(
                reason_code="invalid_hooks_metadata",
                message="hooks frontmatter must be a mapping",
                skill_name=resolved_name,
            ),
        )

    issues: list[SkillLoadIssue] = []
    matchers: list[SkillHookMatcher] = []
    unsupported_events: list[str] = []
    for event_name in sorted(value):
        normalized_event = _HOOK_EVENT_ALIASES.get(str(event_name))
        if normalized_event is None:
            unsupported_events.append(str(event_name))
            issues.append(
                SkillLoadIssue(
                    reason_code="unsupported_skill_hook_event",
                    message=f"Unsupported skill hook event '{event_name}' for the current Aether hook substrate",
                    skill_name=resolved_name,
                    metadata={"supported_events": list(_SUPPORTED_HOOK_EVENTS)},
                )
            )
        raw_matchers = value[event_name]
        if not isinstance(raw_matchers, list):
            issues.append(
                SkillLoadIssue(
                    reason_code="invalid_hooks_metadata",
                    message=f"hooks.{event_name} must be a list of matcher entries",
                    skill_name=resolved_name,
                )
            )
            continue
        for index, raw_matcher in enumerate(raw_matchers):
            if not isinstance(raw_matcher, Mapping):
                issues.append(
                    SkillLoadIssue(
                        reason_code="invalid_hooks_metadata",
                        message=f"hooks.{event_name}[{index}] must be a mapping",
                        skill_name=resolved_name,
                    )
                )
                continue
            matcher_text = _coerce_optional_string(raw_matcher.get("matcher")) or ""
            raw_hooks = raw_matcher.get("hooks")
            if not isinstance(raw_hooks, list) or not raw_hooks:
                issues.append(
                    SkillLoadIssue(
                        reason_code="invalid_hooks_metadata",
                        message=f"hooks.{event_name}[{index}].hooks must be a non-empty list",
                        skill_name=resolved_name,
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
                    SkillLoadIssue(
                        reason_code="invalid_hooks_metadata",
                        message=f"hooks.{event_name}[{index}].hooks entries must be strings or mappings",
                        skill_name=resolved_name,
                    )
                )
            if hook_commands:
                matchers.append(
                    SkillHookMatcher(
                        original_event=str(event_name),
                        normalized_event=normalized_event,
                        matcher=matcher_text,
                        hooks=tuple(hook_commands),
                    )
                )
    return SkillHookMetadata(matchers=tuple(matchers), unsupported_events=tuple(unsupported_events)), tuple(issues)


def _relative_posix_path(file_path: str | Path, resolved_cwd: Path) -> str | None:
    candidate = Path(file_path).resolve()
    try:
        relative = candidate.relative_to(resolved_cwd)
    except ValueError:
        return None
    value = relative.as_posix()
    return value or None


def _matches_pattern(relative_path: str, pattern: str) -> bool:
    try:
        return Path(relative_path).match(pattern)
    except ValueError:
        return False


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


register_mcp_skill_builders(
    MCPSkillBuilders(
        create_skill_spec=create_skill_spec,
        parse_skill_frontmatter_fields=parse_skill_frontmatter_fields,
    )
)


__all__ = [
    "LoadedFrom",
    "ParsedSkillFrontmatter",
    "SkillExecutionContext",
    "SkillHookCommand",
    "SkillHookEvent",
    "SkillHookMatcher",
    "SkillHookMetadata",
    "SkillLoadIssue",
    "SkillLoadResult",
    "SkillSource",
    "SkillSpec",
    "create_skill_spec",
    "discover_skill_directories_for_paths",
    "estimate_skill_frontmatter_tokens",
    "load_skills_from_directory",
    "parse_frontmatter_document",
    "parse_skill_frontmatter_fields",
    "skill_matches_paths",
]
