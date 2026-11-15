"""view_image's limits are one bound: pixels. M1 census (15 Nov): a 30 MB byte cap refused a 4000x4000 PPM (48 MB, 16 M
pixels) in 27 runs of one task. Known-bads: the old byte cap refuses that image; a header claiming too many pixels
is still refused before decoding; a file past the byte bound is refused before it is copied."""

import asyncio

import pytest

from aether.core import images
from tests.core_fakes import LocalEnv

pytest.importorskip("PIL")


def ppm(path, w, h, body=True):
    with open(path, "wb") as fh:
        fh.write(f"P6\n{w} {h}\n255\n".encode())
        if body:
            fh.write(bytes([200, 30, 30]) * (w * h))


def test_a_large_uncompressed_image_within_the_pixel_bound_is_shown(tmp_path):
    ppm(tmp_path / "big.ppm", 4000, 4000)
    assert (tmp_path / "big.ppm").stat().st_size > 30_000_000  # the case the old cap refused
    desc, url = asyncio.run(images.load(LocalEnv(tmp_path), str(tmp_path / "big.ppm")))
    assert "4000x4000" in desc and "shown at 1024x1024" in desc and url.startswith("data:image/png;base64,")


def test_a_header_claiming_too_many_pixels_is_refused_before_decoding(tmp_path):
    ppm(tmp_path / "bomb.ppm", 9000, 9000, body=False)
    with pytest.raises(ValueError, match="pixel limit"):
        asyncio.run(images.load(LocalEnv(tmp_path), str(tmp_path / "bomb.ppm")))


def test_a_file_past_the_byte_bound_is_refused_before_it_is_copied(tmp_path):
    with open(tmp_path / "huge.bin", "wb") as fh:
        fh.truncate(images.MAX_FILE_BYTES + 1)  # sparse: no real bytes written
    env = LocalEnv(tmp_path)
    with pytest.raises(ValueError, match="the limit is"):
        asyncio.run(images.load(env, str(tmp_path / "huge.bin")))
    assert len(env.commands) == 1  # only the size check ran
