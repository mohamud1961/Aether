"""Route modality as a measured fact in the run contract (master checklist M4, multi-format plan 15 Nov).

Whether a route accepts image parts is a property of the deployment, measured once (a known-answer probe, or
recorded runs that sent image parts and were answered). ``AETHER_CORE_ROUTE_MODALITY`` names a JSON record of
that measurement::

    {"deployment": "gpt-6-luna", "images": true, "evidence": "..."}

When it is set, the run starts only if the record is for this run's deployment and ``AETHER_CORE_IMAGES`` equals
the measured value. Anything else stops the run before any model call, so a mismatch surfaces as a configuration
failure instead of a mid-run provider rejection read as a model failure. Unset, nothing is checked (stock).
"""

from __future__ import annotations

import json
from typing import Mapping

ROUTE_MODALITY_ENV = "AETHER_CORE_ROUTE_MODALITY"


class RouteModalityError(RuntimeError):
    pass


def check(environ: Mapping[str, str], *, deployment: str, images: bool) -> str:
    """Return a one-line fact for the run record, or raise when the record is missing, malformed or disagrees."""
    path = environ.get(ROUTE_MODALITY_ENV, "").strip()
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError) as exc:
        raise RouteModalityError(f"{ROUTE_MODALITY_ENV}={path}: cannot read the route record ({exc})") from exc
    if not isinstance(record, dict) or not isinstance(record.get("deployment"), str) \
            or not isinstance(record.get("images"), bool) or not str(record.get("evidence") or "").strip():
        raise RouteModalityError(f"{ROUTE_MODALITY_ENV}={path}: needs deployment (text), images (true/false) and evidence")
    if record["deployment"] != deployment:
        raise RouteModalityError(
            f"{ROUTE_MODALITY_ENV}={path} was measured for deployment {record['deployment']!r}, "
            f"but this run uses {deployment!r}; measure this deployment or point at its record")
    if record["images"] != images:
        measured = "accepts" if record["images"] else "does not accept"
        raise RouteModalityError(
            f"route {deployment!r} {measured} image parts (measured: {record['evidence']}), "
            f"but AETHER_CORE_IMAGES={'on' if images else 'off'}; set it to {'on' if record['images'] else 'off'}")
    return f"route {deployment}: images {'on' if images else 'off'} matches the measured route ({record['evidence']})"
