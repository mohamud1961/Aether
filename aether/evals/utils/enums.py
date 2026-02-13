from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Set


@dataclass(frozen=True)
class EnumViolation:
    enum_name: str
    value: object
    reason: str
    known_values: List[str]


class EnumRegistry:
    def __init__(self, values: Mapping[str, Iterable[str]], source_path: Optional[Path] = None) -> None:
        self._values: Dict[str, Set[str]] = {
            name: {str(item) for item in items}
            for name, items in values.items()
        }
        self.source_path = source_path

    @classmethod
    def load(cls, enum_registry_path: str | Path) -> "EnumRegistry":
        path = Path(enum_registry_path)
        if path.is_dir():
            path = path / "enum_registry.json"

        if not path.exists():
            return cls({}, source_path=path)

        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("enum_registry.json must be a JSON object")

        if "enums" in raw:
            enum_values = raw["enums"]
        else:
            enum_values = raw

        if not isinstance(enum_values, dict):
            raise ValueError("enum_registry enums field must be a JSON object")

        normalized: Dict[str, List[str]] = {}
        for name, values in enum_values.items():
            if not isinstance(values, list):
                raise ValueError(f"Enum values for {name} must be a list")
            normalized[str(name)] = sorted({str(item) for item in values})

        return cls(normalized, source_path=path)

    def known(self, enum_name: str) -> List[str]:
        return sorted(self._values.get(enum_name, set()))

    def has_enum(self, enum_name: str) -> bool:
        return enum_name in self._values

    def validate(self, enum_name: str, value: object) -> bool:
        if enum_name not in self._values:
            return False
        return str(value) in self._values[enum_name]

    def require(self, enum_name: str, value: object) -> None:
        if enum_name not in self._values:
            violation = EnumViolation(
                enum_name=enum_name,
                value=value,
                reason="unknown_enum_name",
                known_values=[],
            )
            raise AssertionError(violation)

        if not self.validate(enum_name, value):
            violation = EnumViolation(
                enum_name=enum_name,
                value=value,
                reason="unknown_enum_value",
                known_values=self.known(enum_name),
            )
            raise AssertionError(violation)

    def to_dict(self) -> Dict[str, List[str]]:
        return {name: sorted(values) for name, values in sorted(self._values.items())}
