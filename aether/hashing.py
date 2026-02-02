import hashlib
import json
from typing import Any


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    from datetime import datetime
    from enum import Enum
    from pathlib import Path
    from dataclasses import is_dataclass, asdict

    if isinstance(obj, (datetime)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def canonical_json_bytes(value: Any) -> bytes:
    try:
        serialized = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=json_serial,
        )
    except TypeError as exc:
        import sys
        print(f"DEBUG: JSON failed for: {value}", file=sys.stderr)
        raise ValueError("Value is not JSON serializable") from exc
    return serialized.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_canonical_json(value: Any) -> str:
    return sha256_hex(canonical_json_bytes(value))
