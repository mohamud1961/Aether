"""image_effort: only the request that first sees a newly attached image uses the given reasoning effort."""

from __future__ import annotations

import pytest

from aether.core.loop import CoreConfig
from tests.core_fakes import call
from tests.test_core_v2 import _run


def _png(path):
    from PIL import Image

    Image.new("RGB", (40, 20), (0, 0, 255)).save(path, format="PNG")


def _efforts(tmp_path, config):
    (tmp_path / "work").mkdir()
    _png(tmp_path / "work" / "a.png")
    script = [
        call("terminal", {"input": "true"}, "c1"),
        call("view_image", {"path": "a.png"}, "c2"),
        call("terminal", {"input": "true"}, "c3"),
        call("finish", {"summary": "x"}, "c4"),
    ]
    _, _, client = _run(tmp_path, script, config=config)
    return [r.get("reasoning_effort") for r in client.requests]


def test_the_request_after_an_image_uses_image_effort(tmp_path):
    pytest.importorskip("PIL")
    efforts = _efforts(tmp_path, CoreConfig(images=True, image_effort="xhigh"))
    assert len(efforts) == 4
    assert efforts[2] == "xhigh"  # the request that first carries the image
    assert efforts[3] != "xhigh" and efforts[0] != "xhigh" and efforts[1] != "xhigh"  # others: the run's own


def test_off_by_default(tmp_path):
    pytest.importorskip("PIL")
    assert "xhigh" not in _efforts(tmp_path, CoreConfig(images=True))
