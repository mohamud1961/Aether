"""Real client/HTTP protocol tests against an explicitly scripted loopback server; no model calls."""

import asyncio
from collections import deque
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

from openai import AsyncOpenAI
import pytest

from aether.core.calls import CallLog, requests
from aether.core.provider import ChatProvider, ProviderError


@contextmanager
def server(replies):
    seen = []
    queue = deque(replies)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            seen.append(
                json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            )
            status, headers, body = queue.popleft()
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{http.server_port}", seen
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


def sse(parts):
    chunks = []
    for delta, finish in parts:
        chunks.append(
            {
                "id": "loopback-response",
                "object": "chat.completion.chunk",
                "model": "scripted",
                "created": 1,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
        )
    body = (
        "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
    )
    return 200, {"Content-Type": "text/event-stream"}, body.encode()


def test_real_sdk_assembles_fragmented_calls_closes_stream_and_logs_exact_json(
    tmp_path,
):
    parts = [
        (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "x",
                        "type": "function",
                        "function": {"name": "write_", "arguments": '{"path":'},
                    }
                ]
            },
            None,
        ),
        (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "function": {
                            "name": "file",
                            "arguments": '"out","content":"hello"}',
                        },
                    }
                ]
            },
            None,
        ),
        ({}, "tool_calls"),
    ]
    with server([sse(parts)]) as (url, seen):

        async def go():
            async with AsyncOpenAI(
                api_key="offline-fixture-key",
                base_url=url + "/openai/v1/",
                max_retries=0,
            ) as client:
                streams = []

                class Capture:
                    async def create(self, **kw):
                        stream = await client.chat.completions.create(**kw)
                        streams.append(stream)
                        return stream

                from types import SimpleNamespace

                provider = ChatProvider(
                    SimpleNamespace(chat=SimpleNamespace(completions=Capture())),
                    model="scripted",
                    params={},
                    log=CallLog(tmp_path / "calls"),
                )
                turn = await provider.complete(
                    [{"role": "user", "content": "task"}],
                    [],
                    max_tokens=20,
                    remaining_s=lambda: 10,
                )
                assert streams[0].response.is_closed
                assert turn.tool_calls[0]["function"]["name"] == "write_file"
                assert json.loads(turn.tool_calls[0]["function"]["arguments"]) == {
                    "path": "out",
                    "content": "hello",
                }

        asyncio.run(go())
        (row,) = requests(tmp_path / "calls")
        assert row["request"] == seen[0] and row["response_id"] == "loopback-response"
        assert "offline-fixture-key" not in (tmp_path / "calls").read_text()


def test_real_sdk_early_eof_is_failed_keeps_partial_content_and_is_retried(tmp_path):
    # B1 seq-assembly: one cut stream ended the run; nothing from it was dispatched, so it is retried
    cut = sse([({"content": "partial"}, None)])
    whole = sse([({"content": "complete"}, "stop")])
    with server([cut, whole]) as (url, seen):

        async def go():
            async with AsyncOpenAI(
                api_key="fixture", base_url=url + "/openai/v1/", max_retries=0
            ) as client:
                provider = ChatProvider(
                    client,
                    model="scripted",
                    params={},
                    log=CallLog(tmp_path / "calls"),
                    sleep=lambda s: asyncio.sleep(0),
                )
                return await provider.complete(
                    [], None, max_tokens=20, remaining_s=lambda: 10
                )

        turn = asyncio.run(go())
        first, second = requests(tmp_path / "calls")
        assert first["ok"] is False and first["response"]["content"] == "partial"
        assert second["ok"] is True and turn.content == "complete" and len(seen) == 2


def test_a_stream_cut_on_every_attempt_still_ends_honestly(tmp_path, monkeypatch):
    from aether.core import provider as P

    monkeypatch.setattr(P, "MAX_ATTEMPTS", 2)
    cut = sse([({"content": "partial"}, None)])
    with server([cut, cut]) as (url, seen):

        async def go():
            async with AsyncOpenAI(
                api_key="fixture", base_url=url + "/openai/v1/", max_retries=0
            ) as client:
                provider = ChatProvider(
                    client,
                    model="scripted",
                    params={},
                    log=CallLog(tmp_path / "calls"),
                    sleep=lambda s: asyncio.sleep(0),
                )
                with pytest.raises(ProviderError, match="finish_reason"):
                    await provider.complete(
                        [], None, max_tokens=20, remaining_s=lambda: 10
                    )

        asyncio.run(go())
        assert [r["ok"] for r in requests(tmp_path / "calls")] == [False, False]
        assert len(seen) == 2


