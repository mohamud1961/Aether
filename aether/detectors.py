from __future__ import annotations

import re
import shlex
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .artifact_store import ArtifactStore

_COMPLETION_PATTERNS = [
    re.compile(r"\b(done|complete|completed|finished|ready)\b"),
    re.compile(r"\btests? pass\b"),
    re.compile(r"\bsolution (is )?complete\b"),
    re.compile(r"\bboth (versions )?work\b"),
]

_PERMISSION_PATTERNS = [
    re.compile(r"\bshould i proceed\b"),
    re.compile(r"\bmay i proceed\b"),
    re.compile(r"\bdo you want me to\b"),
    re.compile(r"\bwould you like me to\b"),
]

_TEST_ALLOWLIST: Sequence[Sequence[str]] = (
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
    ("pytest",),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("npm", "test"),
    ("pnpm", "test"),
    ("yarn", "test"),
)


def detect_completion_signals(
    message: str,
    *,
    artifact_store: Optional[ArtifactStore] = None,
) -> List[Dict[str, Any]]:
    normalized = _normalize_for_detection(message)
    if not _matches_any(normalized, _COMPLETION_PATTERNS):
        return []

    message_ref = _store_message_ref(message, artifact_store)
    signal: Dict[str, Any] = {
        "type": "completion",
        "source": "assistant_message",
    }
    if message_ref is not None:
        signal["message_ref"] = message_ref
    return [signal]


def detect_permission_request_signals(
    message: str,
    *,
    artifact_store: Optional[ArtifactStore] = None,
) -> List[Dict[str, Any]]:
    normalized = _normalize_for_detection(message)
    if not _matches_any(normalized, _PERMISSION_PATTERNS):
        return []

    argv_prefix_signature = _extract_command_signature(message)
    if argv_prefix_signature is None:
        return []

    message_ref = _store_message_ref(message, artifact_store)
    signal: Dict[str, Any] = {
        "type": "permission_request",
        "source": "assistant_message",
        "argv_prefix_signature": argv_prefix_signature,
    }
    if message_ref is not None:
        signal["message_ref"] = message_ref
    return [signal]


def _test_execution_detected_impl(command: Iterable[str], exit_code: Optional[int]) -> bool:
    if exit_code != 0:
        return False

    argv = [str(item) for item in command]
    if not argv:
        return False

    for prefix in _TEST_ALLOWLIST:
        if len(argv) >= len(prefix) and argv[: len(prefix)] == list(prefix):
            return True
    return False


# Backward-compatible exported name; mark as non-test so pytest won't collect it.
test_execution_detected = _test_execution_detected_impl
test_execution_detected.__test__ = False


def evidence_success_detected(
    *,
    verifier_result: Optional[Dict[str, Any]] = None,
    current_workspace_fingerprint_hash: Optional[str] = None,
    verifier_plan_id: Optional[str] = None,
) -> bool:
    if not verifier_result:
        return False
    if verifier_result.get("status") != "pass":
        return False
    if verifier_result.get("workspace_fingerprint_hash") != current_workspace_fingerprint_hash:
        return False
    if verifier_plan_id is not None and verifier_plan_id == "":
        return False
    return True


def completion_claim_truthful(
    *,
    completion_detected: bool,
    verifier_result: Optional[Dict[str, Any]] = None,
    current_workspace_fingerprint_hash: Optional[str] = None,
    verifier_plan_id: Optional[str] = None,
) -> bool:
    if not completion_detected:
        return False
    return evidence_success_detected(
        verifier_result=verifier_result,
        current_workspace_fingerprint_hash=current_workspace_fingerprint_hash,
        verifier_plan_id=verifier_plan_id,
    )


def verification_hint_detected(
    *,
    completion_detected: bool,
    test_execution_detected: bool,
) -> bool:
    return completion_detected or test_execution_detected


def semantic_success_detected(
    *,
    completion_detected: bool,
    test_execution_passed: bool,
    verifier_result: Optional[Dict[str, Any]] = None,
    current_workspace_fingerprint_hash: Optional[str] = None,
    verifier_plan_id: Optional[str] = None,
) -> bool:
    return completion_claim_truthful(
        completion_detected=completion_detected,
        verifier_result=verifier_result,
        current_workspace_fingerprint_hash=current_workspace_fingerprint_hash,
        verifier_plan_id=verifier_plan_id,
    )


def _matches_any(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    for pattern in patterns:
        if pattern.search(text):
            return True
    return False


def _normalize_for_detection(text: str) -> str:
    stripped = _strip_code_blocks_and_quotes(text)
    lowered = stripped.lower()
    collapsed = re.sub(r"\s+", " ", lowered).strip()
    return collapsed


def _strip_code_blocks_and_quotes(text: str) -> str:
    lines = text.splitlines()
    kept: List[str] = []
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith(">"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _extract_command_signature(text: str) -> Optional[List[str]]:
    lines = text.splitlines()
    in_fence = False
    fence_lines: List[str] = []

    def commit_fence() -> Optional[List[str]]:
        for raw in fence_lines:
            candidate = raw.strip()
            if not candidate:
                continue
            if candidate.startswith("$"):
                candidate = candidate[1:].strip()
            argv = _tokenize_command(candidate)
            if argv:
                return argv
        return None

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_fence:
                signature = commit_fence()
                if signature:
                    return signature
                fence_lines.clear()
                in_fence = False
            else:
                in_fence = True
                fence_lines.clear()
            continue

        if in_fence:
            fence_lines.append(line)
            continue

        if stripped.startswith("$"):
            candidate = stripped[1:].strip()
            argv = _tokenize_command(candidate)
            if argv:
                return argv

    if in_fence:
            argv = commit_fence()
            if argv:
                return argv

    return None


def _tokenize_command(text: str) -> Optional[List[str]]:
    try:
        parts = shlex.split(text, posix=True)
    except ValueError:
        return None
    if not parts:
        return None
    tool = _normalize_tool_name(parts[0])
    if not tool:
        return None
    return [tool] + parts[1:]


def _normalize_tool_name(token: str) -> str:
    cleaned = token.strip()
    if "\\" in cleaned:
        cleaned = cleaned.replace("\\", "/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    return cleaned.lower()


def _store_message_ref(message: str, artifact_store: Optional[ArtifactStore]) -> Optional[str]:
    if artifact_store is None:
        return None
    artifact = artifact_store.put_bytes(message.encode("utf-8"), content_type="text/plain")
    return artifact.artifact_id
