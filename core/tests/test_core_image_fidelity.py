"""AETHER_CORE_IMAGE_FIDELITY=original: full-size images at detail "original", more images kept (G7 freecad, 17 Nov).

Known-bads each test must refuse: the default path shrinking a 1448 px drawing is kept (switch off changes nothing);
the switch on still shrinking it, dropping the detail field on the Responses wire, or keeping only 2 images."""

import base64
import io

import pytest

from aether.core import harbor_config as hc
from aether.core import images
from aether.core.responses import _parts

PIL = pytest.importorskip("PIL.Image")

BASE = {hc.REVIEW_ENV: "off", hc.CONTEXT_ENV: "clm", hc.REPL_ENV: "off", hc.IMAGES_ENV: "on"}


def png(w, h):
    out = io.BytesIO()
    PIL.new("RGB", (w, h), (10, 200, 10)).save(out, format="PNG")
    return out.getvalue()


def shown_size(url):
    return PIL.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size


def test_the_switch_is_off_by_default_and_wires_keep_and_fidelity():
    off = hc.build_config(environ=BASE)
    assert off.image_fidelity == "standard" and off.clm.image_keep == images.KEEP_IMAGES
    on = hc.build_config(environ={**BASE, hc.IMAGE_FIDELITY_ENV: "original"})
    assert on.image_fidelity == "original" and on.clm.image_keep == images.FULL_KEEP
    with pytest.raises(hc.ConfigError):
        hc.build_config(environ={**BASE, hc.IMAGE_FIDELITY_ENV: "huge"})


def test_default_shrinks_a_drawing_and_original_keeps_its_size():
    data = png(1448, 1024)
    desc, url = images.encode(data, "/app/d.png")
    assert shown_size(url) == (1024, 724) and "shown at 1024x724" in desc
    desc, url = images.encode(data, "/app/d.png", max_side=images.FULL_MAX_SIDE)
    assert shown_size(url) == (1448, 1024) and "shown at" not in desc


def test_detail_reaches_the_responses_wire_only_when_set():
    plain = _parts(images.message("d", "data:image/png;base64,AA==")["content"])
    assert plain[1] == {"type": "input_image", "image_url": "data:image/png;base64,AA=="}
    full = _parts(images.message("d", "data:image/png;base64,AA==", images.FULL_DETAIL)["content"])
    assert full[1]["detail"] == "original"
    pair = _parts(images.comparison_message("a", "u1", "b", "u2", "original")["content"])
    assert [p.get("detail") for p in pair if p["type"] == "input_image"] == ["original", "original"]


def test_keep_bounds_how_many_images_stay_in_the_request():
    msgs = [images.message(f"img{i}", "data:image/png;base64,AA==") for i in range(10)]
    count = lambda out: sum(isinstance(m["content"], list) for m in out)
    assert count(images.limit(msgs)) == 2
    assert count(images.limit(msgs, keep=images.FULL_KEEP)) == 8
