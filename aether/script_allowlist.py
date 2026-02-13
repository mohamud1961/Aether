from __future__ import annotations

from typing import Set

from .hashing import sha256_hex


def check_script_allowed(script_content: str, allowlist_hashes: Set[str]) -> bool:
    if not allowlist_hashes:
        return False
    script_hash = sha256_hex(script_content.encode("utf-8"))
    return script_hash in allowlist_hashes
