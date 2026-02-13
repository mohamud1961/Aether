from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Sequence

# V1.1 layer-oriented section constants.
SECTION_POLICY_V11 = "POLICY"
SECTION_SYSTEM_V11 = "SYSTEM"
SECTION_CONTRACTS = "CONTRACTS"
SECTION_TASK_V11 = "TASK"
SECTION_PLAN_V11 = "PLAN"
SECTION_EVIDENCE_V11 = "EVIDENCE"
SECTION_STATE_V11 = "STATE"
SECTION_SCRATCH_V11 = "SCRATCH"

# Legacy section constants retained for compatibility with existing callers/tests.
SECTION_DOCTRINE = "Doctrine"
SECTION_POLICY = "Policy"
SECTION_TASK = "TaskSpec"
SECTION_PLAN = "Plan"
SECTION_VERIFICATION = "Verification"
SECTION_EVIDENCE = "Evidence"
SECTION_STATE = "State"
SECTION_SCRATCH = "Scratch"
SECTION_UNTRUSTED = "UntrustedData"
SECTION_CONFLICTS = "Conflicts"

LAYER_ORDER = (
    SECTION_POLICY_V11,
    SECTION_SYSTEM_V11,
    SECTION_CONTRACTS,
    SECTION_TASK_V11,
    SECTION_PLAN_V11,
    SECTION_EVIDENCE_V11,
    SECTION_STATE_V11,
    SECTION_SCRATCH_V11,
)

STATIC_SECTIONS = (
    SECTION_DOCTRINE,
    SECTION_POLICY,
    SECTION_TASK,
    SECTION_PLAN,
)
EVIDENCE_SECTIONS = (
    SECTION_VERIFICATION,
    SECTION_EVIDENCE,
)
STATE_SECTIONS = (SECTION_STATE,)
SCRATCH_SECTIONS = (
    SECTION_SCRATCH,
    SECTION_UNTRUSTED,
    SECTION_CONFLICTS,
)
MODEL_SECTION_ORDER = LAYER_ORDER + STATIC_SECTIONS + EVIDENCE_SECTIONS + STATE_SECTIONS + SCRATCH_SECTIONS

PROJECTION_DOCTRINE_SECTIONS = (
    SECTION_POLICY_V11,
    SECTION_SYSTEM_V11,
)
PROJECTION_STABLE_SECTIONS = (
    SECTION_CONTRACTS,
    SECTION_TASK_V11,
    SECTION_PLAN_V11,
    SECTION_EVIDENCE_V11,
)
PROJECTION_STATE_SECTIONS = (SECTION_STATE_V11,)
PROJECTION_SCRATCH_SECTIONS = (SECTION_SCRATCH_V11,)
PROJECTION_RENDER_SECTIONS = (
    PROJECTION_DOCTRINE_SECTIONS
    + PROJECTION_STABLE_SECTIONS
    + PROJECTION_STATE_SECTIONS
    + PROJECTION_SCRATCH_SECTIONS
)

TRUSTED_SECTIONS = {
    SECTION_POLICY_V11,
    SECTION_SYSTEM_V11,
    SECTION_CONTRACTS,
    SECTION_TASK_V11,
    SECTION_PLAN_V11,
    SECTION_EVIDENCE_V11,
    SECTION_STATE_V11,
    SECTION_DOCTRINE,
    SECTION_POLICY,
    SECTION_TASK,
    SECTION_PLAN,
    SECTION_VERIFICATION,
    SECTION_EVIDENCE,
    SECTION_STATE,
}

_CACHE_VOLATILE_KEYS = {
    "observed_at",
    "validity_ttl",
    "content_hash",
}


class ContextPackProjection:
    """
    Deterministic model-facing projection built only from compiled context.

    This keeps volatile state/scratch late in the prompt for provider prefix caching.
    """

    def __init__(self, compiled_context_pack: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self._compiled = {
            str(section): [dict(item) for item in items]
            for section, items in compiled_context_pack.items()
        }

        self._doctrine_items = self._build_doctrine_items()
        self._conversation_items = self._build_conversation_items()
        self._stable_prefix_text = self._build_stable_prefix_text()

    def get_tier_items(self, tier: str) -> List[Dict[str, Any]]:
        if tier == "DOCTRINE":
            return [dict(item) for item in self._doctrine_items]
        if tier == "CONVERSATION":
            return [dict(item) for item in self._conversation_items]
        return []

    @property
    def stable_prefix_bytes(self) -> bytes:
        return self._stable_prefix_text.encode("utf-8")

    @property
    def section_bytes(self) -> Dict[str, int]:
        """
        Byte size for each rendered section block.

        Values are based on rendered prompt sections (including section wrappers).
        Sections with no items are reported as zero.
        """
        counts: Dict[str, int] = {}
        seen = set()

        for section in MODEL_SECTION_ORDER:
            seen.add(section)
            counts[section] = self._section_rendered_bytes(section)

        # Include any non-standard sections that may appear in compiled context packs.
        for section in sorted(self._compiled.keys()):
            if section in seen:
                continue
            counts[section] = self._section_rendered_bytes(section)

        return counts

    def _build_doctrine_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for section in PROJECTION_DOCTRINE_SECTIONS:
            for item in self._compiled.get(section, []):
                content = item.get("content")
                if isinstance(content, str) and content:
                    items.append({"content": content})
        return items

    def _build_conversation_items(self) -> List[Dict[str, Any]]:
        conversation: List[Dict[str, Any]] = []

        stable_block = self._render_sections(list(PROJECTION_STABLE_SECTIONS), cache_safe=True)
        if stable_block:
            conversation.append({"role": "user", "content": stable_block})

        state_block = self._render_sections(list(PROJECTION_STATE_SECTIONS))
        if state_block:
            conversation.append({"role": "user", "content": state_block})

        scratch_block = self._render_sections(list(PROJECTION_SCRATCH_SECTIONS))
        if scratch_block:
            conversation.append({"role": "user", "content": scratch_block})

        if not conversation:
            conversation.append({"role": "user", "content": "[TASK]\nNo task content provided."})
        return conversation

    def _build_stable_prefix_text(self) -> str:
        blocks = []
        doctrine = "\n\n".join(item.get("content", "") for item in self._doctrine_items if item.get("content"))
        if doctrine:
            blocks.append(doctrine)
        rendered = self._render_sections(list(PROJECTION_STABLE_SECTIONS), cache_safe=True)
        if rendered:
            blocks.append(rendered)
        return "\n\n".join(blocks)

    def _render_sections(self, sections: List[str], *, cache_safe: bool = False) -> str:
        chunks: List[str] = []
        for section in sections:
            items = self._compiled.get(section, [])
            if not items:
                continue
            chunks.append(self._render_section(section, items, cache_safe=cache_safe))
        return "\n\n".join(chunk for chunk in chunks if chunk)

    def _render_section(
        self,
        section: str,
        items: Sequence[Mapping[str, Any]],
        *,
        cache_safe: bool = False,
    ) -> str:
        lines = [f"<<SECTION:{section}:BEGIN>>", f"[{section}]"]
        if section == SECTION_STATE_V11:
            lines.extend(self._render_tool_receipts_block(items))
        for item in items:
            if section == SECTION_STATE_V11 and item.get("kind") == "tool_output_summary":
                continue
            content = self._render_item_content(item, section=section, cache_safe=cache_safe)

            pointer_bits: List[str] = []
            source_artifact = item.get("source_artifact_id")
            source_hash = item.get("source_hash")
            span = item.get("span")
            if isinstance(source_artifact, str) and source_artifact:
                pointer_bits.append(f"source_artifact_id={source_artifact}")
            if isinstance(source_hash, str) and source_hash:
                pointer_bits.append(f"source_hash={source_hash}")
            if isinstance(span, dict):
                offset = span.get("offset")
                length = span.get("length")
                if isinstance(offset, int) and isinstance(length, int):
                    pointer_bits.append(f"span={offset}:{length}")

            source_ref = item.get("source_ref")
            authority = item.get("authority_tier")
            if isinstance(source_ref, str) and source_ref:
                lines.append(f"- source_ref={source_ref}")
            if isinstance(authority, str) and authority:
                lines.append(f"- authority_tier={authority}")
            if pointer_bits:
                lines.append("- pointers: " + ", ".join(pointer_bits))

            lines.append(content)

        if section in SCRATCH_SECTIONS:
            lines.insert(1, "- NOTE: non-authoritative scratch/untrusted data")
        if section == SECTION_SCRATCH_V11:
            lines.insert(1, "- NOTE: non-authoritative scratch/untrusted data")
        if section == SECTION_PLAN_V11:
            lines.insert(1, "- NOTE: plan updates require explicit backtrack to Plan phase")
        lines.append(f"<<SECTION:{section}:END>>")
        return "\n".join(lines)

    def _render_tool_receipts_block(self, items: Sequence[Mapping[str, Any]]) -> List[str]:
        tool_receipts = [item for item in items if item.get("kind") == "tool_output_summary"]
        if not tool_receipts:
            return ["tool_receipts: []"]

        lines = ["tool_receipts:"]
        for receipt in tool_receipts:
            rendered = self._render_tool_summary_item(receipt)
            if rendered:
                lines.append(f"- {rendered}")
        if len(lines) == 1:
            lines.append("- none")
        return lines

    def _render_item_content(
        self,
        item: Mapping[str, Any],
        *,
        section: str,
        cache_safe: bool = False,
    ) -> str:
        if item.get("kind") == "state_readiness":
            rendered_readiness = self._render_state_readiness_item(item)
            if rendered_readiness:
                return rendered_readiness
        if item.get("kind") == "advisory_memo":
            rendered_memo = self._render_advisory_memo_item(item)
            if rendered_memo:
                return rendered_memo
        if item.get("kind") == "tool_output_summary":
            rendered_summary = self._render_tool_summary_item(item)
            if rendered_summary:
                return rendered_summary
        if item.get("kind") == "conflicts":
            rendered = self._render_conflict_item(item)
            if rendered:
                return rendered

        content = item.get("content", "")
        if isinstance(content, str):
            if cache_safe and section in PROJECTION_STABLE_SECTIONS:
                return self._sanitize_structured_text_for_cache(content)
            return content
        if isinstance(content, (dict, list)):
            if cache_safe and section in PROJECTION_STABLE_SECTIONS:
                content = self._strip_cache_volatile_metadata(content)
            return json.dumps(content, sort_keys=True, separators=(",", ":"))
        if content is None:
            # CONTRACTS digest slots can be represented as structured fields without free-text content.
            digest_slots = {
                "intent_contract_digest": item.get("intent_contract_digest"),
                "completion_contract_digest": item.get("completion_contract_digest"),
                "plan_digest": item.get("plan_digest"),
            }
            present = {k: v for k, v in digest_slots.items() if v is not None}
            return json.dumps(present, sort_keys=True, separators=(",", ":")) if present else ""
        return str(content)

    def _render_state_readiness_item(self, item: Mapping[str, Any]) -> str:
        content = item.get("content")
        if not isinstance(content, Mapping):
            return ""
        summary = str(content.get("state_summary", "")).strip()
        readiness = content.get("readiness")
        if not isinstance(readiness, Mapping):
            readiness = {}

        def _flag(name: str) -> str:
            return "true" if bool(readiness.get(name)) else "false"

        readiness_line = (
            "readiness: {"
            f"explore_floor_passed={_flag('explore_floor_passed')}, "
            f"plan_approved={_flag('plan_approved')}, "
            f"needs_verify={_flag('needs_verify')}, "
            f"can_review={_flag('can_review')}"
            "}"
        )
        denial_code = str(content.get("last_denial_code", "NONE")).strip() or "NONE"
        lines = [summary or "STATE_SUMMARY phase=UNKNOWN denial=NONE readiness=E0P0V0R0", readiness_line]
        lines.append(f"last_denial_code: {denial_code}")
        return "\n".join(lines)

    def _render_tool_summary_item(self, item: Mapping[str, Any]) -> str:
        content = item.get("content")
        if not isinstance(content, Mapping):
            return ""
        renderable = dict(content)
        rendered = json.dumps(
            renderable,
            sort_keys=True,
            separators=(",", ":"),
        )
        command_synopsis = renderable.get("command_synopsis")
        if isinstance(command_synopsis, str) and command_synopsis.strip():
            return f"Tool receipt summary: command_synopsis={command_synopsis.strip()}; payload={rendered}"
        return "Tool receipt summary: " + rendered

    def _render_advisory_memo_item(self, item: Mapping[str, Any]) -> str:
        content = item.get("content")
        if not isinstance(content, Mapping):
            return ""
        entries = content.get("entries")
        if not isinstance(entries, list):
            return (
                "Advisory Memo (non-authoritative; non-governance-driving): "
                + json.dumps(dict(content), sort_keys=True, separators=(",", ":"))
            )

        lines: List[str] = ["Advisory Memo (non-authoritative; non-governance-driving):"]
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            observed_at = str(entry.get("observed_at", ""))
            tool_name = str(entry.get("tool_name", ""))
            note = str(entry.get("assistant_note", ""))
            lines.append(
                f"{observed_at} | tool={tool_name} | note={json.dumps(note, ensure_ascii=True)}"
            )
        return "\n".join(lines)

    def _render_conflict_item(self, item: Mapping[str, Any]) -> str:
        conflicts = item.get("conflicts")
        if not isinstance(conflicts, list):
            return ""

        lines: List[str] = ["Conflict deltas (deterministic):"]
        normalized_conflicts = sorted(
            (entry for entry in conflicts if isinstance(entry, Mapping)),
            key=lambda entry: str(entry.get("conflict_key", "")),
        )
        for conflict in normalized_conflicts:
            key = str(conflict.get("conflict_key", ""))
            refs = sorted(
                str(ref)
                for ref in conflict.get("source_refs", [])
                if isinstance(ref, str) and ref
            )
            lines.append(f"- conflict_key={key}")
            lines.append(f"  source_refs={', '.join(refs)}")
        return "\n".join(lines)

    def _section_rendered_bytes(self, section: str) -> int:
        if section not in PROJECTION_RENDER_SECTIONS:
            return 0
        items = self._compiled.get(section, [])
        if not items:
            return 0
        rendered = self._render_section(
            section,
            items,
            cache_safe=section in PROJECTION_STABLE_SECTIONS,
        )
        return len(rendered.encode("utf-8"))

    def _sanitize_structured_text_for_cache(self, text: str) -> str:
        stripped = text.strip()
        if not stripped:
            return text
        if stripped[0] not in "{[":
            return text
        try:
            parsed = json.loads(text)
        except Exception:
            return text
        sanitized = self._strip_cache_volatile_metadata(parsed)
        return json.dumps(sanitized, sort_keys=True, separators=(",", ":"))

    def _strip_cache_volatile_metadata(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            sanitized: Dict[str, Any] = {}
            for key in sorted(value.keys()):
                if key in _CACHE_VOLATILE_KEYS:
                    continue
                sanitized[key] = self._strip_cache_volatile_metadata(value[key])
            return sanitized
        if isinstance(value, list):
            return [self._strip_cache_volatile_metadata(item) for item in value]
        return value
