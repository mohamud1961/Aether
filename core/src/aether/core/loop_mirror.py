"""The context mirror is written while the model call is in flight, not after it.

Each turn the mirror file (CLM, ``clm.settings.mirror_path``) holds the history before that turn's assistant message,
which is exactly the history the request carries. Cost scan 16 Nov: writing it after the reply put one sandbox
round trip (median 0.33 s) on the critical path before every tool dispatch. ``start`` begins the same write as the
request goes out; ``write`` then uses it only when the text is byte-identical to what the turn would have written,
and otherwise writes as before, so the file and its digest are unchanged either way. Writes never overlap: an
earlier write is always awaited before another to the same path.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from .env import put_bytes


def start(s: Any) -> None:
    """Begin writing the mirror of the history the coming request holds (CLM only)."""
    if not s.clm or s.mirror_prewrite is not None:
        return
    upto = len(s.clm.editable)
    text = s.clm.render(upto)
    task = asyncio.ensure_future(put_bytes(s.env, text.encode(), s.clm.settings.mirror_path))
    s.mirror_prewrite = (upto, text, task)


async def settle(s: Any) -> None:
    """Let an unused write finish (its outcome is superseded by the next write); call before another ``start``."""
    pre, s.mirror_prewrite = s.mirror_prewrite, None
    if pre is not None:
        with contextlib.suppress(Exception):
            await pre[2]


def abandon(s: Any) -> None:
    """At run end: cancel a write still in flight."""
    pre, s.mirror_prewrite = s.mirror_prewrite, None
    if pre is not None and not pre[2].done():
        pre[2].cancel()
    elif pre is not None and not pre[2].cancelled():
        pre[2].exception()  # retrieved, so an unused failed write is not reported as never awaited


async def write(s: Any, upto: int, text: str) -> None:
    """Make the mirror hold ``text``; raises as the direct write would."""
    pre, s.mirror_prewrite = s.mirror_prewrite, None
    if pre is not None:
        if (pre[0], pre[1]) == (upto, text):
            await pre[2]
            return
        with contextlib.suppress(Exception):  # an outdated write lands first, then the current text replaces it
            await pre[2]
    await put_bytes(s.env, text.encode(), s.clm.settings.mirror_path)
