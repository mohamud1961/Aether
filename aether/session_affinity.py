"""Opt-in infrastructure arm: route one row's provider requests to the same replica.

The GLM Fireworks/Azure route spreads requests over replicas, so the prompt cache hits only
by luck. Sending an opaque ``x-session-affinity`` HTTP header keeps a row on one replica and
makes repeated prefixes cache. This is transport only: the header is an SDK request option
(``extra_headers``) and never enters the model-facing payload, snapshot, or token accounting.

``AETHER_G4_SESSION_AFFINITY`` selects ``control`` (default, no header) or ``run_v1``; under
``run_v1`` the launcher sets ``AETHER_PROVIDER_SESSION_AFFINITY`` to the row's run id. The
M-TREE compactor and CHALLENGER card callables use ``<run_id>:compactor`` / ``<run_id>:challenger``.
"""
from __future__ import annotations

import argparse
import re
from hashlib import sha256
from typing import Any, Mapping

CONTROL = "control"
RUN_V1 = "run_v1"
SUPPORTED_SESSION_AFFINITY_MODES = frozenset({CONTROL, RUN_V1})
SESSION_AFFINITY_ENV = "AETHER_G4_SESSION_AFFINITY"
SESSION_AFFINITY_KEY_ENV = "AETHER_PROVIDER_SESSION_AFFINITY"
SESSION_AFFINITY_HEADER = "x-session-affinity"
_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class SessionAffinityError(ValueError):
    """An unknown mode or an invalid key was supplied."""


def resolve_session_affinity_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(SESSION_AFFINITY_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_SESSION_AFFINITY_MODES:
        raise SessionAffinityError(f"unknown session-affinity mode: {selected!r}")
    return selected


def validate_session_affinity_key(key: str) -> str:
    """1-128 chars of [A-Za-z0-9._:-]. The value is never echoed into the error."""
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise SessionAffinityError("session affinity key must be 1-128 characters of [A-Za-z0-9._:-]")
    return key


def session_affinity_key_from_env(
    environ: Mapping[str, str], *, suffix: str = "",
) -> str | None:
    """Key for one callable: the env key (plus ``:suffix``), or None when none is configured."""
    raw = environ.get(SESSION_AFFINITY_KEY_ENV)
    if raw is None or raw == "":
        return None
    key = raw if not suffix else f"{raw}:{suffix}"
    return validate_session_affinity_key(key)


def key_sha256_12(key: str) -> str:
    return sha256(key.encode("utf-8")).hexdigest()[:12]


def merge_affinity_headers(dispatch_request: dict[str, Any], key: str | None) -> dict[str, Any]:
    """Return a dispatch request carrying the header; the input mapping is never mutated."""
    if key is None:
        return dispatch_request
    merged = dict(dispatch_request)
    headers = dict(merged.get("extra_headers") or {})
    headers[SESSION_AFFINITY_HEADER] = key
    merged["extra_headers"] = headers
    return merged


def check_selector_matches_key(mode: str, environ: Mapping[str, str]) -> None:
    """Fail closed: run_v1 needs a valid key, control must have none, so no row is silently unlabeled."""
    key = environ.get(SESSION_AFFINITY_KEY_ENV)
    present = key is not None and key != ""
    if mode == RUN_V1:
        if not present:
            raise SessionAffinityError(f"{SESSION_AFFINITY_ENV}={RUN_V1} requires {SESSION_AFFINITY_KEY_ENV}")
        validate_session_affinity_key(str(key))
    elif present:
        raise SessionAffinityError(f"{SESSION_AFFINITY_KEY_ENV} is set but {SESSION_AFFINITY_ENV} is {CONTROL}")


def add_session_affinity_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--session-affinity", choices=sorted(SUPPORTED_SESSION_AFFINITY_MODES), default=CONTROL,
        help="send the row's run id as x-session-affinity so requests share one replica (opt-in)",
    )


def build_session_affinity_launch_binding(mode: str | None, *, run_id: str = "") -> dict[str, Any]:
    """Validate, then return child env and manifest identity."""
    selected = resolve_session_affinity_mode(mode)
    env = {SESSION_AFFINITY_ENV: selected}
    manifest: dict[str, Any] = {"session_affinity": selected}
    if selected == RUN_V1:
        key = validate_session_affinity_key(str(run_id))
        env[SESSION_AFFINITY_KEY_ENV] = key
        manifest["session_affinity_config"] = {
            "header": SESSION_AFFINITY_HEADER,
            "key_source": "run_id",
            "key_sha256_12": key_sha256_12(key),
            "suffixes": ["compactor", "challenger"],
        }
    return {"session_affinity": selected, "env": env, "manifest": manifest}
