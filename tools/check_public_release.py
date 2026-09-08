#!/usr/bin/env python3
"""Fail closed on obvious publication hazards in the tracked public release.

This checker is intentionally conservative about current reviewer-facing surfaces.
Historical research and exact frozen evidence may contain old local-path references,
but credentials, sensitive filenames, obsolete current-tree products, and local
machine paths in the current runtime/docs/site are release blockers.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = (
    "README.md",
    "PUBLIC_REVIEWER_GUIDE.md",
    "aether/__init__.py",
    "docs/ARCHITECTURE.md",
    "docs/SAFETY_BOUNDARY.md",
    "docs/QUALIFICATION.md",
    "docs/DEVELOPMENT_HISTORY.md",
    "docs/RESEARCH_PROGRAMME.md",
    "docs/GETTING_STARTED.md",
    "evidence/README.md",
    "evidence/qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json",
    "evidence/terminal-bench/configure-git-webserver/README.md",
    "evidence/safety/workspace-boundary-rejection/README.md",
    "website/public/funding-cards.html",
)

RETIRED_CURRENT_SURFACES = ("harness", "eval_suite", "variants", "workflows")

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
LOCAL_PATH_PATTERNS = (
    re.compile(r"/Users/[A-Za-z0-9_.-]+/"),
    re.compile(r"/home/[A-Za-z0-9_.-]+/"),
    re.compile(r"/private/tmp/"),
    re.compile(r"\.gateway-runtime/worktrees"),
    re.compile(r"/mnt/data/"),
)
LOCAL_PATH_EXEMPT_PREFIXES = (
    "research/",  # explicitly historical archive
    "tracking/",  # exact frozen evidence authority; hashes must remain stable
    "tools/",     # release checkers contain the path-pattern literals they enforce
)


def tracked_files() -> list[str]:
    return subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()


def is_text(path: Path) -> tuple[bool, str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return False, ""
    if b"\0" in raw[:4096]:
        return False, ""
    try:
        return True, raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, ""


def main() -> None:
    files = tracked_files()
    failures: list[str] = []

    for rel in REQUIRED_PATHS:
        if rel not in files:
            failures.append(f"required public path missing: {rel}")

    for root_name in RETIRED_CURRENT_SURFACES:
        if any(rel == root_name or rel.startswith(root_name + "/") for rel in files):
            failures.append(f"retired current-tree surface returned: {root_name}/")

    for rel in files:
        lower = rel.lower()
        if any(part in lower for part in SENSITIVE_NAME_PARTS):
            failures.append(f"sensitive filename: {rel}")

        path = ROOT / rel
        text_ok, text = is_text(path)
        if not text_ok:
            continue

        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"credential-like content ({label}): {rel}")

        if not rel.startswith(LOCAL_PATH_EXEMPT_PREFIXES):
            for pattern in LOCAL_PATH_PATTERNS:
                if pattern.search(text):
                    failures.append(f"local-machine path in current public surface: {rel}")
                    break

    if failures:
        print("PUBLIC_RELEASE_INVALID")
        for failure in sorted(set(failures)):
            print(failure)
        raise SystemExit(1)

    print(
        "PUBLIC_RELEASE_VALID "
        f"tracked_files={len(files)} credential_findings=0 sensitive_filenames=0 "
        f"retired_surfaces=0 current_local_paths=0"
    )


if __name__ == "__main__":
    main()
