"""Exact model-facing interface capture and compact composition manifests.

This module is instrumentation only. It never rewrites, reorders, truncates, or
otherwise changes messages before provider dispatch. Exact transcripts are kept
separately from compact manifests so run records can remain inspectable without
embedding every prompt byte inline.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from .attention_projection import attention_projection_policy
from .model_profile import PRODUCTION_PROFILE


MODEL_INTERFACE_SCHEMA_VERSION = "aether_model_interface.v1"
_SECTION_RE = re.compile(r"^\[([^\]\n]{1,120})\]\n")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    )


def _sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _token_estimate_v1(text: str) -> int:
    """Stable coarse estimate used only for relative interface accounting."""
    byte_count = len(text.encode("utf-8"))
    return max(1, (byte_count + 3) // 4) if text else 0


def _section_name(content: str) -> str:
    match = _SECTION_RE.match(content)
    return match.group(1) if match else ""


def _json_top_level_keys(content: str) -> list[str]:
    try:
        value = json.loads(content)
    except Exception:
        return []
    if not isinstance(value, Mapping):
        return []
    return [str(key) for key in value.keys()]


def build_model_interface_capture(
    messages: Iterable[Mapping[str, Any]],
    *,
    model_role: str,
    role_call_ordinal: int,
    max_output_tokens: int | None,
    stable_prefix_count: int = 0,
) -> dict[str, Any]:
    """Capture the exact transcript and a content-neutral composition manifest."""
    exact_messages = [
        {
            "role": str(item.get("role", "")),
            "content": str(item.get("content", "")),
        }
        for item in messages
    ]
    stable_prefix_count = max(0, min(int(stable_prefix_count), len(exact_messages)))
    rows: list[dict[str, Any]] = []
    hash_to_indices: dict[str, list[int]] = {}
    for index, item in enumerate(exact_messages):
        content = item["content"]
        content_hash = _sha256_text(content)
        hash_to_indices.setdefault(content_hash, []).append(index)
        rows.append({
            "index": index,
            "role": item["role"],
            "stable_prefix": index < stable_prefix_count,
            "section_name": _section_name(content),
            "json_top_level_keys": _json_top_level_keys(content),
            "chars": len(content),
            "utf8_bytes": len(content.encode("utf-8")),
            "token_estimate_v1": _token_estimate_v1(content),
            "sha256": content_hash,
        })

    stable_rows = rows[:stable_prefix_count]
    volatile_rows = rows[stable_prefix_count:]

    def totals(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "messages": len(items),
            "chars": sum(int(item["chars"]) for item in items),
            "utf8_bytes": sum(int(item["utf8_bytes"]) for item in items),
            "token_estimate_v1": sum(int(item["token_estimate_v1"]) for item in items),
        }

    aggregate = totals(rows)
    stable = totals(stable_rows)
    volatile = totals(volatile_rows)
    total_bytes = aggregate["utf8_bytes"]
    duplicates = [
        {"sha256": digest, "message_indices": indices}
        for digest, indices in sorted(hash_to_indices.items())
        if len(indices) > 1
    ]
    transcript_payload = {
        "model_role": str(model_role),
        "role_call_ordinal": int(role_call_ordinal),
        "messages": exact_messages,
    }
    manifest = {
        "schema_version": MODEL_INTERFACE_SCHEMA_VERSION,
        "model_role": str(model_role),
        "role_call_ordinal": int(role_call_ordinal),
        "max_output_tokens": (int(max_output_tokens) if max_output_tokens is not None else None),
        "message_count": len(rows),
        "stable_prefix_count": stable_prefix_count,
        "role_sequence": [item["role"] for item in rows],
        "section_sequence": [
            item["section_name"] for item in rows if item["section_name"]
        ],
        "messages": rows,
        "aggregate": aggregate,
        "stable_prefix": stable,
        "volatile": volatile,
        "stable_prefix_byte_ratio": (
            round(stable["utf8_bytes"] / total_bytes, 6) if total_bytes else 0.0
        ),
        "exact_duplicate_messages": duplicates,
        "attention_projection": {"mode": attention_projection_policy()["mode"]},
        "model_profile": PRODUCTION_PROFILE.manifest(),
        "model_profile_sha256": PRODUCTION_PROFILE.sha256(),
        "transcript_sha256": _sha256_text(_stable_json(transcript_payload)),
    }
    return {
        "schema_version": MODEL_INTERFACE_SCHEMA_VERSION,
        "manifest": manifest,
        "messages": exact_messages,
    }


def compact_model_interface_manifests(
    captures: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        dict(capture.get("manifest", {}))
        for capture in captures
        if isinstance(capture.get("manifest"), Mapping)
    ]


def write_model_interface_captures(
    captures: Iterable[Mapping[str, Any]],
    destination: str | Path,
) -> dict[str, Any]:
    """Write exact transcripts as separate files and one compact index."""
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    index_rows: list[dict[str, Any]] = []
    for ordinal, capture in enumerate(captures, start=1):
        manifest = dict(capture.get("manifest", {}) or {})
        role = _SAFE_NAME_RE.sub("_", str(manifest.get("model_role", "model"))).strip("_") or "model"
        role_ordinal = int(manifest.get("role_call_ordinal", ordinal) or ordinal)
        filename = f"{ordinal:04d}_{role}_{role_ordinal:04d}.json"
        path = root / filename
        payload = {
            "schema_version": MODEL_INTERFACE_SCHEMA_VERSION,
            "manifest": manifest,
            "messages": [
                {
                    "role": str(item.get("role", "")),
                    "content": str(item.get("content", "")),
                }
                for item in capture.get("messages", ())
                if isinstance(item, Mapping)
            ],
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index_rows.append({
            "ordinal": ordinal,
            "model_role": manifest.get("model_role", ""),
            "role_call_ordinal": manifest.get("role_call_ordinal", 0),
            "path": filename,
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "transcript_sha256": manifest.get("transcript_sha256", ""),
            "aggregate": manifest.get("aggregate", {}),
            "stable_prefix": manifest.get("stable_prefix", {}),
            "volatile": manifest.get("volatile", {}),
        })
    index = {
        "schema_version": "aether_model_interface_index.v1",
        "capture_count": len(index_rows),
        "captures": index_rows,
    }
    index_path = root / "index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "directory": str(root),
        "index_path": str(index_path),
        "index_sha256": sha256(index_path.read_bytes()).hexdigest(),
        "capture_count": len(index_rows),
    }
