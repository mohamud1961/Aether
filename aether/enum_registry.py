from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, Mapping, Optional, Set

from .hashing import hash_canonical_json


DEFAULT_ENUM_REGISTRY_PATH = Path(__file__).with_name("enum_registry.json")


@dataclass(frozen=True)
class EnumRegistry:
    values: Dict[str, Set[str]]
    aliases: Dict[str, Dict[str, str]]
    source_path: Path
    registry_hash: str

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "EnumRegistry":
        source_path = (path or DEFAULT_ENUM_REGISTRY_PATH).resolve()
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("enum_registry.json must be a JSON object")

        enums_raw = payload.get("enums", payload)
        if not isinstance(enums_raw, dict):
            raise ValueError("enum_registry enums field must be a JSON object")

        aliases_raw = payload.get("aliases", {})
        if not isinstance(aliases_raw, dict):
            raise ValueError("enum_registry aliases field must be a JSON object")

        values: Dict[str, Set[str]] = {}
        for name, items in enums_raw.items():
            if not isinstance(items, list):
                raise ValueError(f"Enum values for {name} must be a list")
            values[str(name)] = {str(item) for item in items}

        aliases: Dict[str, Dict[str, str]] = {}
        for enum_name, mapping in aliases_raw.items():
            if not isinstance(mapping, dict):
                raise ValueError(f"Aliases for {enum_name} must be an object")
            aliases[str(enum_name)] = {
                str(key).strip().lower(): str(value)
                for key, value in mapping.items()
            }

        registry_hash = hash_canonical_json(payload)
        return cls(
            values=values,
            aliases=aliases,
            source_path=source_path,
            registry_hash=registry_hash,
        )

    def validate_enum(self, enum_name: str, value: object) -> bool:
        enum = self.values.get(enum_name)
        if enum is None:
            return False

        if enum_name == "event_type":
            return self.canonicalize_event_type(value) is not None

        if value is None:
            return False
        return str(value) in enum

    def get_enum_values(self, enum_name: str) -> Set[str]:
        return set(self.values.get(enum_name, set()))

    def canonicalize_event_type(self, value: object) -> Optional[str]:
        event_types = self.values.get("event_type", set())
        if not isinstance(value, str):
            return None

        candidate = value.strip()
        if not candidate:
            return None
        if candidate in event_types:
            return candidate

        alias_map = self.aliases.get("event_type", {})
        mapped = alias_map.get(candidate.lower())
        if mapped in event_types:
            return mapped

        # Case-insensitive exact canonical match fallback.
        lowered = candidate.lower()
        for known in event_types:
            if known.lower() == lowered:
                return known
        return None


_DEFAULT_REGISTRY: Optional[EnumRegistry] = None
_DEFAULT_REGISTRY_LOCK = Lock()


def load_enum_registry(path: Optional[Path] = None) -> EnumRegistry:
    global _DEFAULT_REGISTRY
    if path is not None:
        return EnumRegistry.load(path)

    if _DEFAULT_REGISTRY is None:
        with _DEFAULT_REGISTRY_LOCK:
            if _DEFAULT_REGISTRY is None:
                _DEFAULT_REGISTRY = EnumRegistry.load()
    return _DEFAULT_REGISTRY


def validate_enum(enum_name: str, value: object, *, registry: Optional[EnumRegistry] = None) -> bool:
    active = registry or load_enum_registry()
    return active.validate_enum(enum_name, value)


def get_enum_values(enum_name: str, *, registry: Optional[EnumRegistry] = None) -> Set[str]:
    active = registry or load_enum_registry()
    return active.get_enum_values(enum_name)


def enum_registry_hash(*, registry: Optional[EnumRegistry] = None) -> str:
    active = registry or load_enum_registry()
    return active.registry_hash
