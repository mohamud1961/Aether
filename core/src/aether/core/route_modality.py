"""Route modality as a measured fact in the run contract (master checklist M4, multi-format plan 15 Nov).

Whether a route accepts image parts is a property of the deployment, measured once (a known-answer probe, or
recorded runs that sent image parts and were answered). ``AETHER_CORE_ROUTE_MODALITY`` names a JSON record of
that measurement::

    {"deployment": "gpt-6-luna", "images": true, "evidence": "..."}

When it is set, the record must match the deployment. Image tools require a route measured to accept images.
An image-capable route also supports a text-only tool profile. Unset, nothing is checked (stock).
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
    if images and not record["images"]:
        raise RouteModalityError(
            f"route {deployment!r} does not accept image parts (measured: {record['evidence']}), "
            "but AETHER_CORE_IMAGES=on; set it to off")
    if images:
        return f"route {deployment}: images on matches the measured route ({record['evidence']})"
    measured = "accepts" if record["images"] else "does not accept"
    return f"route {deployment}: images off; measured route {measured} image parts ({record['evidence']})"
