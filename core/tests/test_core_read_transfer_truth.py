"""Known-bad transfer controls for model-visible text reads and image viewing."""

from __future__ import annotations

import asyncio
import base64
import io
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def _run_tool(
    tmp_path: Path,
    work: Path,
    env: LocalEnv,
    action_name: str,
    args: dict,
    *,
    images=False,
):
    control = tmp_path / "control"
    control.mkdir(exist_ok=True)
    action_id = "inspect-action"
    client = ScriptedClient(
        [
            call(action_name, args, action_id),
            call("finish", {"summary": "Done"}, "finish"),
        ]
    )
    result = asyncio.run(
        run_agent(
            env=env,
            task="Inspect the requested artifact faithfully.",
            workdir=str(work),
            provider=ChatProvider(client, model="offline-script", params={}),
            timeout_s=30,
            trace=Trace(tmp_path / f"{action_name}.jsonl"),
            config=CoreConfig(images=images, control_dir=str(control), record=False),
        )
    )
    messages = client.requests[1]["messages"]
    tool_messages = [
        m
        for m in messages
        if m.get("role") == "tool" and m.get("tool_call_id") == action_id
    ]
    assert len(tool_messages) == 1
    return result, tool_messages[0]["content"], messages, client


class SubstituteImageTransfer(LocalEnv):
    """At the Environment download boundary, return another same-size valid image."""

    def __init__(self, root: Path, source: Path, substitute: Path):
        super().__init__(root)
        self.source = source
        self.substitute = substitute
        self.fired = False
        self.transferred = b""

    async def download_file(self, source_path, target_path):
        if Path(source_path) == self.source:
            self.fired = True
            self.transferred = self.substitute.read_bytes()
            Path(target_path).write_bytes(self.transferred)
            return
        return await super().download_file(source_path, target_path)


def test_view_image_rejects_same_size_valid_but_wrong_pixel_transfer(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    work = tmp_path / "work"
    work.mkdir()
    source, substitute = work / "frame.bmp", tmp_path / "substitute.bmp"
    Image.new("RGB", (24, 16), (230, 20, 30)).save(source, format="BMP")
    Image.new("RGB", (24, 16), (10, 40, 220)).save(substitute, format="BMP")
    source_bytes = source.read_bytes()
    assert len(source_bytes) == len(substitute.read_bytes()), (
        "fault must preserve transfer length"
    )
    env = SubstituteImageTransfer(work, source, substitute)

    result, visible, messages, _ = _run_tool(
        tmp_path, work, env, "view_image", {"path": "frame.bmp"}, images=True
    )

    assert env.fired
    assert source.read_bytes() == source_bytes, (
        "the source oracle must remain independent"
    )
    image_messages = [
        part
        for message in messages
        if isinstance(message.get("content"), list)
        for part in message["content"]
        if isinstance(part, dict) and part.get("type") == "image_url"
    ]
    if image_messages:
        from PIL import Image

        url = image_messages[-1]["image_url"]["url"]
        decoded = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
        assert decoded.getpixel((5, 5))[:3] == (230, 20, 30), (
            "view_image must show pixels from the path's observed source bytes, "
            "not a valid same-size substitute"
        )
    else:
        assert visible.startswith("error:") and any(
            word in visible.lower()
            for word in ("verify", "integrity", "differ", "mismatch")
        ), visible
    assert result.status == "finished"


class CorruptReadResponse(LocalEnv):
    """Alter only the environment's returned base64 page, not the source file."""

    def __init__(self, root: Path, mode: str):
        super().__init__(root)
        self.mode = mode
        self.fired = False

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        result = await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)
        if self.fired or "base64 <" not in command or result.return_code != 0:
            return result
        self.fired = True
        lines = result.stdout.splitlines()
        assert len(lines) >= 2, (
            f"expected a read page and base64 body: {result.stdout!r}"
        )
        total = lines[0]
        if len(lines) >= 3 and re.fullmatch(r"[0-9a-f]{64}", lines[1]):
            digest, encoded = lines[1], "".join(lines[2:])
            digest_prefix = f"{digest}\n"
        else:  # baseline before source-page digest protocol
            digest_prefix, encoded = "", "".join(lines[1:])
        if self.mode == "same_length_substitute":
            raw = base64.b64decode(encoded)
            assert b"ORIGINAL" in raw
            altered = raw.replace(b"ORIGINAL", b"CORRUPT!", 1)
            assert len(altered) == len(raw)
            encoded = base64.b64encode(altered).decode("ascii")
        elif self.mode == "malformed_base64":
            encoded = "?" + encoded
        stdout = f"{total}\n{digest_prefix}{encoded}\n"
        return SimpleNamespace(
            return_code=result.return_code, stdout=stdout, stderr=result.stderr
        )


@pytest.mark.parametrize(
    ("mode", "source_text"),
    [
        ("same_length_substitute", "ORIGINAL source bytes\n"),
        ("malformed_base64", "ORIGINAL source bytes\n"),
    ],
)
def test_read_file_never_presents_unverified_transfer_as_source(
    tmp_path, mode, source_text
):
    work = tmp_path / "work"
    work.mkdir()
    source = work / "evidence.txt"
    source.write_text(source_text)
    env = CorruptReadResponse(work, mode)

    result, visible, _, _ = _run_tool(
        tmp_path, work, env, "read_file", {"path": source.name}
    )

    assert env.fired, "fault must modify the actual read response"
    assert source.read_text() == source_text
    assert "CORRUPT!" not in visible
    if mode == "same_length_substitute":
        assert visible.startswith("error:") or "ORIGINAL" in visible, visible
    else:
        assert visible.startswith("error:"), (
            f"malformed base64 must be rejected: {visible}"
        )
    assert result.status == "finished"


def test_image_fifo_is_refused_before_any_download_or_blocking_read(tmp_path):
    import os

    from aether.core import images

    source = tmp_path / "pipe"
    os.mkfifo(source)

    class NoSpecialDownload(LocalEnv):
        async def download_file(self, source_path, target_path):
            raise AssertionError("nonregular image reached download")

    with pytest.raises(ValueError, match="regular file"):
        asyncio.run(
            asyncio.wait_for(
                images.load(NoSpecialDownload(tmp_path), str(source)), timeout=1
            )
        )
