"""Let the model look at image files in the sandbox.

Probe, 12 Oct 2026: the GLM-5.3-Flash deployment answers image questions correctly
(teal vs no-image control; left/right halves; square position), at ~40-60 prompt tokens
for a 64x64 image. Prime Agent has the same capability (``attach_image``).

The file is read from the container and re-encoded on the host as PNG (so BMP, PPM,
TGA etc. work), downscaled to at most MAX_SIDE. Only the newest KEEP_IMAGES images
stay in a request; older ones become a one-line placeholder, and the context-file
mirror never contains image data.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import re
import shlex
from copy import deepcopy
from typing import Any

from .env import Environment, run
from .transfer import get_bytes

MAX_PIXELS = (
    40_000_000  # checked from the header before decoding (decompression-bomb guard)
)
# The pixel bound is the real limit; the byte bound only has to admit any image within it, stored uncompressed
# (4 bytes a pixel plus a header). M1 census, 15 Nov: a 30 MB byte cap refused a 4000x4000 PPM (48 MB, 16 M
# pixels) in 48 of 72 view_image errors across 27 runs of one task, though it was well inside the pixel bound.
MAX_FILE_BYTES = MAX_PIXELS * 4 + 1_000_000
MAX_SIDE = 1024
KEEP_IMAGES = 2
HISTORY_FIELD = "aether_image_history"
IMAGE_TOKENS = 1_500  # conservative per-image cost used by the context budget
IMAGE_CHARS = int(IMAGE_TOKENS * 3)


async def _source_sha256(env: Environment, path: str) -> str:
    """Hash the environment-side bytes so a valid but altered download is rejected."""
    q = shlex.quote(path)
    result = await run(
        env,
        f"(sha256sum < {q} 2>/dev/null || shasum -a 256 < {q})",
    )
    fields = result.stdout.split()
    if result.code != 0 or not fields or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
        raise ValueError(
            f"{path} source bytes could not be verified; image was not shown"
        )
    return fields[0]


def available() -> bool:
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        return False
    return True


async def load(env: Environment, path: str, region: list[int] | None = None) -> tuple[str, str]:
    """Return (description, data URL). Raises with a plain reason the model can act on. ``region``: crop to
    [left, top, right, bottom] of the source pixels before any downscale (image_region)."""
    # Size is checked inside the sandbox, before anything is copied to the host.
    res = await run(
        env,
        f"if [ ! -f {shlex.quote(path)} ]; then echo 'not a regular file' >&2; exit 2; fi; "
        f"stat -c %s {shlex.quote(path)} 2>/dev/null || wc -c < {shlex.quote(path)}",
    )
    if res.code != 0:
        raise ValueError(f"{path} is not a readable regular file")
    try:
        nbytes = int(res.stdout.split()[0])
    except (IndexError, ValueError):
        raise ValueError(f"{path} does not exist or cannot be read") from None
    if nbytes > MAX_FILE_BYTES:
        raise ValueError(f"{path} is {nbytes} bytes; the limit is {MAX_FILE_BYTES}")
    data = await get_bytes(env, path)
    if len(data) > MAX_FILE_BYTES:  # the file grew between the check and the copy
        raise ValueError(f"{path} is {len(data)} bytes; the limit is {MAX_FILE_BYTES}")
    source_digest = await _source_sha256(env, path)
    if hashlib.sha256(data).hexdigest() != source_digest:
        raise ValueError(
            f"{path} transfer differs from observed source bytes; image was not shown"
        )
    return encode(data, path, region)


def encode(data: bytes, path: str, region: list[int] | None = None) -> tuple[str, str]:
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))  # lazy: reads the header only
        width, height = img.size
        if width * height > MAX_PIXELS:
            raise ValueError(f"{width}x{height} exceeds the {MAX_PIXELS}-pixel limit")
        img.load()
    except Exception as exc:
        raise ValueError(
            f"{path} is not a readable image ({type(exc).__name__}: {exc})"
        ) from exc
    fmt, size, mode = img.format, img.size, img.mode
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    img = img.convert("RGBA" if "A" in mode else "RGB")
    box = None
    if region is not None:
        from .image_region import check

        box = check(region, size)
        img = img.crop(box)
        zoom = min(4, MAX_SIDE // max(img.size))  # small text reads better enlarged
        if zoom > 1:
            img = img.resize((img.size[0] * zoom, img.size[1] * zoom), Image.LANCZOS)
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="PNG")
    crop = f", region {list(box)}" if box else ""
    native = box and img.size == (box[2] - box[0], box[3] - box[1])
    if box and not native and img.size[0] > box[2] - box[0]:
        crop += f", enlarged {img.size[0] // (box[2] - box[0])}x to {img.size[0]}x{img.size[1]}"
        native = True
    shown = crop + ("" if img.size == size or native else f", shown at {img.size[0]}x{img.size[1]}")
    desc = f"{path}: {fmt} {size[0]}x{size[1]} {mode}{shown}"
    return desc, "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def message(desc: str, url: str) -> dict[str, Any]:
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": f"[view_image] {desc}"},
            {"type": "image_url", "image_url": {"url": url}},
        ],
    }


async def compare(env: Environment, path: str, region: list[int] | None,
                  other_path: str, other_region: list[int] | None) -> tuple[str, str, str, str]:
    """Finish both reads before attaching either image."""
    first, second = await asyncio.gather(load(env, path, region), load(env, other_path, other_region),
                                         return_exceptions=True)
    for result in (first, second):
        if isinstance(result, BaseException):
            raise result
    return (*first, *second)


def comparison_message(desc: str, url: str, other_desc: str, other_url: str) -> dict[str, Any]:
    return {"role": "user", "content": message(desc, url)["content"] + message(other_desc, other_url)["content"]}


def archive_note(message_id: int) -> str:
    return f"[original image observation: history MSG {message_id}; use read_history with show_image=true]"


def with_history_recall(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = deepcopy(tools)
    for tool in out:
        if tool["function"]["name"] == "read_history":
            tool["function"]["parameters"]["properties"]["show_image"] = {
                "type": "boolean", "description": "Show the original image observation instead of JSON text.",
            }
    return out


def _is_image_part(part: Any) -> bool:
    return isinstance(part, dict) and part.get("type") == "image_url"


def text_of(content: Any) -> str:
    """Plain text of a message's content; images become a marker (never base64)."""
    if not isinstance(content, list):
        return str(content or "")
    return "\n".join(
        "[image]"
        if _is_image_part(p)
        else str(p.get("text", ""))
        if isinstance(p, dict)
        else str(p)
        for p in content
    )


def limit(
    messages: list[dict[str, Any]], keep: int = KEEP_IMAGES, batch: int = 1
) -> list[dict[str, Any]]:
    """Retain a recent suffix of image observations within the image budget.

    ``batch`` > 1 (AETHER_CORE_IMAGE_BATCH, default 1): the oldest images leave in groups of ``batch``, so the shown
    set changes once per ``batch`` new images instead of on every new one; between drops up to keep + batch - 1
    images are shown. Cost scan 16 Nov: replacing one older image with a placeholder mid-history re-billed the whole
    request after it uncached (93% of cache-miss tokens on the current boards, up to 28K tokens per drop).
    """
    if batch > 1:
        total = sum(sum(_is_image_part(p) for p in m["content"]) for m in messages if isinstance(m.get("content"), list))
        keep = total - (max(0, total - keep) // batch) * batch
    seen, out = 0, []
    for msg in reversed(messages):
        content = msg.get("content")
        if isinstance(content, list):
            n_images = sum(_is_image_part(part) for part in content)
            if n_images and seen + n_images > keep:
                seen = keep
                msg = deepcopy(msg)
                replacement = "[image no longer shown; call view_image again to see it]"
                if isinstance(msg.get(HISTORY_FIELD), int):
                    replacement = archive_note(msg[HISTORY_FIELD])
                msg["content"] = text_of(content).replace("[image]", replacement)
            elif n_images:
                seen += n_images
        out.append(msg)
    return list(reversed(out))


def size_chars(messages: list[dict[str, Any]]) -> int:
    """JSON size with each image counted at its budget cost instead of its base64 length."""
    n_images = sum(
        1
        for m in messages
        if isinstance(m.get("content"), list)
        for p in m["content"]
        if _is_image_part(p)
    )
    stripped = [
        {**m, "content": text_of(m["content"])}
        if isinstance(m.get("content"), list)
        else m
        for m in messages
    ]
    return len(json.dumps(stripped, ensure_ascii=False)) + n_images * IMAGE_CHARS
