"""view_image `region` (image_region): part of an image at its own resolution, flag-gated."""

from __future__ import annotations

import base64
import io

import pytest

from aether.core.loop import CoreConfig
from tests.core_fakes import call
from tests.test_core_v2 import _run


def _wide(path):
    from PIL import Image

    img = Image.new("RGB", (3000, 100), (255, 0, 0))
    img.paste((0, 0, 255), (2000, 0, 3000, 100))
    img.save(path, format="PNG")


def _shown(client, request):
    from PIL import Image

    msgs = client.requests[request]["messages"]
    tool_i = max(i for i, m in enumerate(msgs) if m.get("role") == "tool")
    url = msgs[tool_i + 1]["content"][1]["image_url"]["url"]
    return msgs[tool_i]["content"], Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def test_region_shows_that_part_at_native_resolution(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    script = [
        call("view_image", {"path": "strip.png"}, "c1"),
        call("view_image", {"path": "strip.png", "region": [2000, 0, 2900, 100]}, "c2"),
        call("finish", {"summary": "x"}, "c3"),
    ]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_region=True))
    whole_desc, whole = _shown(client, 1)
    assert whole.size == (1024, 34) and "shown at 1024x34" in whole_desc  # the default path still shrinks
    desc, part = _shown(client, 2)
    assert part.size == (900, 100)  # native pixels, not a thumbnail
    assert part.getpixel((10, 10)) == (0, 0, 255)  # the requested part, not the left of the image
    assert "region [2000, 0, 2900, 100]" in desc and "shown at" not in desc
    props = client.requests[0]["tools"]
    view = next(t for t in props if t["function"]["name"] == "view_image")
    assert "region" in view["function"]["parameters"]["properties"]


def test_a_small_region_is_enlarged_for_reading(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    script = [
        call("view_image", {"path": "strip.png", "region": [1950, 0, 2050, 50]}, "c1"),
        call("finish", {"summary": "x"}, "c2"),
    ]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_region=True))
    desc, part = _shown(client, 1)
    assert part.size == (400, 200) and "enlarged 4x" in desc
    assert part.getpixel((10, 100)) == (255, 0, 0) and part.getpixel((390, 100)) == (0, 0, 255)


def test_region_outside_the_image_is_refused_plainly(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    script = [
        call("view_image", {"path": "strip.png", "region": [2500, 0, 3500, 100]}, "c1"),
        call("finish", {"summary": "x"}, "c2"),
    ]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_region=True))
    tool = next(m for m in client.requests[1]["messages"] if m.get("role") == "tool")
    assert "outside the 3000x100 image" in tool["content"]


def test_without_the_flag_view_image_has_no_region(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    script = [
        call("view_image", {"path": "strip.png", "region": [0, 0, 10, 10]}, "c1"),
        call("finish", {"summary": "x"}, "c2"),
    ]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True))
    view = next(t for t in client.requests[0]["tools"] if t["function"]["name"] == "view_image")
    assert "region" not in view["function"]["parameters"]["properties"]
    tool = next(m for m in client.requests[1]["messages"] if m.get("role") == "tool")
    assert "unknown argument 'region'" in tool["content"]


def _images_in(client, request):
    msgs = client.requests[request]["messages"]
    tool_i = max(i for i, m in enumerate(msgs) if m.get("role") == "tool")
    return msgs[tool_i]["content"], [p for p in msgs[tool_i + 1]["content"] if p.get("type") == "image_url"]


def test_an_empty_region_means_the_whole_image(tmp_path):
    """16 Nov live: Luna sent `region: []` and got 'region must be [left, top, right, bottom]' (2 calls)."""
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    script = [
        call("view_image", {"path": "strip.png", "region": []}, "c1"),
        call("finish", {"summary": "x"}, "c2"),
    ]
    _, _, client = _run(tmp_path, script, config=CoreConfig(images=True, image_region=True))
    desc, whole = _shown(client, 1)
    assert whole.size == (1024, 34) and "region [" not in desc and "error" not in desc


def test_a_compare_naming_the_same_view_is_shown_once(tmp_path):
    """16 Nov live: 27/27 compare calls named the main image and region again, so each view sent one image twice."""
    pytest.importorskip("PIL")
    (tmp_path / "work").mkdir()
    _wide(tmp_path / "work" / "strip.png")
    same = {"path": "strip.png", "region": [0, 0, 100, 100]}
    script = [
        call("view_image", {**same, "compare": dict(same)}, "c1"),
        call("view_image", {"path": "strip.png", "region": [], "compare": {"path": "./strip.png", "region": []}}, "c2"),
        call("view_image", {**same, "compare": {"path": "strip.png", "region": [2000, 0, 2100, 100]}}, "c3"),
        call("finish", {"summary": "x"}, "c4"),
    ]
    _, _, client = _run(tmp_path, script,
                        config=CoreConfig(images=True, image_region=True, image_compare=True))
    for request in (1, 2):
        result, parts = _images_in(client, request)
        assert len(parts) == 1 and "same image and region" in result
    result, parts = _images_in(client, 3)  # a real comparison still shows both
    assert len(parts) == 2 and "same image" not in result
