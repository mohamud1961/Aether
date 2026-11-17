"""AETHER_CORE_IMAGE_MULTI / AETHER_CORE_IMAGE_EXEMPT (17 Nov, from G9 freecad vs Codex: 23-24 one-image calls per
pass, and a checkpoint mid-reading that dropped the images and led to 7-9 repeat views)."""

from __future__ import annotations

import pytest

from aether.core import images
from aether.core.clm import ClmContext, ClmSettings
from aether.core.loop import CoreConfig
from tests.core_fakes import call
from tests.test_core_image_region import _wide
from tests.test_core_v2 import _run


def _after_last_tool(client, request):
    msgs = client.requests[request]["messages"]
    i = max(k for k, m in enumerate(msgs) if m.get("role") == "tool")
    parts = [p for m in msgs[i + 1:] if isinstance(m.get("content"), list) for p in m["content"]
             if p.get("type") == "image_url"]
    return msgs[i]["content"], parts


def test_one_call_shows_several_images(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    for name in ("a.png", "b.png", "c.png"):
        _wide(tmp_path / "work" / name)
    script = [call("view_image", {"path": "a.png", "more_paths": ["b.png", "c.png"]}, "c1"),
              call("finish", {"summary": "x"}, "c2")]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_multi=True, context="clm",
                                                            clm=ClmSettings(image_keep=8)))
    result, parts = _after_last_tool(client, 1)
    assert len(parts) == 3 and result.startswith("[3 images:") and "not shown" not in result


def test_more_images_than_the_request_keeps_are_trimmed_and_said(tmp_path):
    """Known-bad: with image_keep=2, three images in one view lost the first before the model saw it."""
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    for name in ("a.png", "b.png", "c.png"):
        _wide(tmp_path / "work" / name)
    script = [call("view_image", {"path": "a.png", "more_paths": ["b.png", "c.png"]}, "c1"),
              call("finish", {"summary": "x"}, "c2")]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_multi=True))
    result, parts = _after_last_tool(client, 1)
    assert len(parts) == 2 and "1 more not shown (at most 2 images per view)" in result
    view = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "view_image")
    assert "more_paths" in view["function"]["parameters"]["properties"]


def test_known_bad_without_the_flag_more_paths_is_refused(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "a.png")
    script = [call("view_image", {"path": "a.png", "more_paths": ["a.png"]}, "c1"),
              call("finish", {"summary": "x"}, "c2")]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True))
    result, parts = _after_last_tool(client, 1)
    assert "unknown argument 'more_paths'" in result and parts == []


def test_a_missing_extra_image_shows_none(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "a.png")
    script = [call("view_image", {"path": "a.png", "more_paths": ["nope.png"]}, "c1"),
              call("finish", {"summary": "x"}, "c2")]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_multi=True))
    result, parts = _after_last_tool(client, 1)
    assert parts == [] and "nope.png" in result


def _ctx(exempt):
    ctx = ClmContext(pinned=[], settings=ClmSettings(budget_tokens=10_000, reserve_tokens=0, image_keep=8,
                                                     image_exempt=exempt))
    ctx.append({"role": "user", "content": "task"})
    for i in range(4):
        ctx.append({"role": "assistant", "content": f"look {i}"})
        ctx.append(images.message(f"view {i}", "data:image/png;base64,iVBO"))
    return ctx


def test_kept_images_do_not_count_toward_the_limit_when_exempt():
    counted, exempt = _ctx(False), _ctx(True)
    assert counted.tokens() == exempt.tokens()  # the request itself is unchanged
    gap = counted.held() - exempt.held()
    assert gap == int(4 * images.IMAGE_CHARS / exempt.chars_per_token) and gap > 0
