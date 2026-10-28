"""Optional `region` for view_image: show part of an image at its own resolution.

code-from-image study (28 Oct 2026, 7 runs): every run's first move after seeing the downscaled image was to crop
a region at native resolution, and every one first found no image library in the container (`No module named
'PIL'`); one pass spent ~40 steps building a decoder. Core already decodes images on the host, so cropping there
costs nothing. Off unless AETHER_CORE_IMAGE_REGION=on.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

IMAGE_REGION_ENV = "AETHER_CORE_IMAGE_REGION"
REGION = {
    "type": "array",
    "items": {"type": "integer"},
    "description": "Optional [left, top, right, bottom] in the image's own pixels: show only that part, at full "
    "resolution, and enlarged up to 4x when small (whole images are shrunk to at most 1024 px on the longest side).",
}


def with_region(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = deepcopy(tools)
    for tool in out:
        if tool["function"]["name"] == "view_image":
            tool["function"]["parameters"]["properties"]["region"] = REGION
    return out


def check(region: Any, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """The region as a crop box, or a plain reason it cannot be used."""
    if len(region) != 4:
        raise ValueError("region must be [left, top, right, bottom]")
    left, top, right, bottom = region
    width, height = size
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError(f"region {region} is outside the {width}x{height} image or empty")
    return left, top, right, bottom
