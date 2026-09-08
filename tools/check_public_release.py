#!/usr/bin/env python3
"""Fail closed on obvious publication hazards in the tracked public release."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    "openai_style_secret": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "github_pat": re.compile(r"\b(?:ghp_|github_pat_)[A-Za-z0-9_]{16,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._~-]{24,}"),
    "assigned_secret": re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|secret[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9_./+~=-]{20,}"
    ),
}
SENSITIVE_NAME_PARTS = (".env", "credentials", "secrets", "id_rsa", "id_ed25519")


def tracked_files() -> list[str]:
    return subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()


def main() -> None:
    files = tracked_files()
    name_findings: list[str] = []
    secret_findings: list[tuple[str, str]] = []
    for rel in files:
        lower = rel.lower()
        if any(part in lower for part in SENSITIVE_NAME_PARTS):
            name_findings.append(rel)
        path = ROOT / rel
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:4096]:
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                secret_findings.append((rel, label))

    if name_findings or secret_findings:
        print("PUBLIC_RELEASE_INVALID")
        for rel in name_findings:
            print(f"sensitive filename: {rel}")
        for rel, label in secret_findings:
            print(f"credential-like content ({label}): {rel}")
        raise SystemExit(1)

    print(f"PUBLIC_RELEASE_VALID tracked_files={len(files)} credential_findings=0 sensitive_filenames=0")


if __name__ == "__main__":
    main()
