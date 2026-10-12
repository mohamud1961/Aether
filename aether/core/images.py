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

import base64
from copy import deepcopy
import io
import json
from typing import Any

from .env import Environment, get_bytes

MAX_FILE_BYTES = 30_000_000
MAX_SIDE = 1024
KEEP_IMAGES = 2
IMAGE_TOKENS = 1_500  # conservative per-image cost used by the context budget
IMAGE_CHARS = int(IMAGE_TOKENS * 3)


def available() -> bool:
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        return False
    return True


async def load(env: Environment, path: str) -> tuple[str, str]:
    """Return (description, data URL). Raises with a plain reason the model can act on."""
    from PIL import Image

    data = await get_bytes(env, path)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{path} is {len(data)} bytes; the limit is {MAX_FILE_BYTES}")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        raise ValueError(f"{path} is not a readable image ({type(exc).__name__}: {exc})") from exc
    fmt, size, mode = img.format, img.size, img.mode
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    img = img.convert("RGBA" if "A" in mode else "RGB")
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, format="PNG")
    shown = "" if img.size == size else f", shown at {img.size[0]}x{img.size[1]}"
    desc = f"{path}: {fmt} {size[0]}x{size[1]} {mode}{shown}"
    return desc, "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def message(desc: str, url: str) -> dict[str, Any]:
    return {"role": "user", "content": [{"type": "text", "text": f"[view_image] {desc}"},
                                        {"type": "image_url", "image_url": {"url": url}}]}


def _is_image_part(part: Any) -> bool:
    return isinstance(part, dict) and part.get("type") == "image_url"


def text_of(content: Any) -> str:
    """Plain text of a message's content; images become a marker (never base64)."""
    if not isinstance(content, list):
        return str(content or "")
    return "\n".join("[image]" if _is_image_part(p) else str(p.get("text", "")) if isinstance(p, dict) else str(p)
                     for p in content)


def limit(messages: list[dict[str, Any]], keep: int = KEEP_IMAGES) -> list[dict[str, Any]]:
    """Copy of ``messages`` in which only the newest ``keep`` images remain."""
    seen, out = 0, []
    for msg in reversed(messages):
        content = msg.get("content")
        if isinstance(content, list) and any(_is_image_part(p) for p in content):
            seen += 1
            if seen > keep:
                msg = deepcopy(msg)
                msg["content"] = text_of(content).replace(
                    "[image]", "[image no longer shown; call view_image again to see it]")
        out.append(msg)
    return list(reversed(out))


def size_chars(messages: list[dict[str, Any]]) -> int:
    """JSON size with each image counted at its budget cost instead of its base64 length."""
    n_images = sum(1 for m in messages if isinstance(m.get("content"), list)
                   for p in m["content"] if _is_image_part(p))
    stripped = [{**m, "content": text_of(m["content"])} if isinstance(m.get("content"), list) else m
                for m in messages]
    return len(json.dumps(stripped, ensure_ascii=False)) + n_images * IMAGE_CHARS
