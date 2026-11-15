"""M-T3 (multi-format plan, 15 Nov): on a route that cannot consume images, no request ever carries an image part, every
image observation is a path handle, and Core never states image content it did not compute.

The scripted model makes a PNG in the terminal, asks an MCP server for an image, tries view_image, then finishes. With
``images`` off the requests are scanned for image parts. Known-bad: the same script with ``images`` on does put an image
part in a request, so the scan can see one.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(not os.path.exists("/proc/self/stat"), reason="native Linux qualification")
FIXTURE = str(Path(__file__).with_name("mcp_fixture_server.py"))
INVENTED = ("the image shows", "the picture shows", "image contains", "in the image")


def image_parts(requests):
    parts = 0
    for r in requests:
        for m in r.get("messages") or []:
            content = m.get("content")
            if isinstance(content, list):
                parts += sum(1 for p in content if isinstance(p, dict) and p.get("type") in ("image_url", "input_image"))
    return parts


def run(tmp_path, images: bool):
    pytest.importorskip("PIL")  # the scripted model draws dot.png with it
    spec = {"name": "fx", "transport": "stdio", "url": None, "command": sys.executable, "args": [FIXTURE, "stdio"]}
    script = [
        call("terminal", {"input": "python3 -c \"from PIL import Image; Image.new('RGB', (4, 4), (200, 30, 30)).save('dot.png')\""},
             "make"),
        call("mcp", {"server": "fx", "action": "call", "tool": "shot"}, "shot"),
        call("view_image", {"path": str(tmp_path / "dot.png")}, "view"),
        call("finish", {"summary": "looked"}, "finish"),
    ]
    client = ScriptedClient(script)
    result = asyncio.run(run_agent(
        env=LocalEnv(tmp_path), task="Look at dot.png and report its colour.", workdir=str(tmp_path),
        provider=ChatProvider(client, model="scripted", params={}), timeout_s=60, trace=Trace(tmp_path / "trace.jsonl"),
        config=CoreConfig(control_dir=str(tmp_path / "ctl"), images=images, mcp_servers=(spec,)),
    ))
    tools = [json.loads(line) for line in open(tmp_path / "trace.jsonl") if '"event": "tool"' in line]
    return result, client.requests, {t.get("name"): str(t.get("result") or "") for t in tools}


def test_a_text_only_route_never_receives_image_parts_or_invented_content(tmp_path):
    result, requests, results = run(tmp_path, images=False)
    assert image_parts(requests) == 0
    assert "view_image" not in json.dumps([t["function"]["name"] for t in requests[0].get("tools") or []])
    assert "saved at" in results["mcp"] and "image returned by the server" in results["mcp"]
    assert results["view_image"].startswith("error") and "unknown tool" in results["view_image"]
    shown = json.dumps([m for r in requests for m in r.get("messages") or []]).lower()
    assert not any(w in shown for w in INVENTED)


def test_known_bad_the_scan_sees_image_parts_when_images_are_on(tmp_path):
    _, requests, _ = run(tmp_path, images=True)
    assert image_parts(requests) >= 1


