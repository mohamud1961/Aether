"""Test doubles for Aether Core: a real local shell environment and a scripted provider."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any


class LocalEnv:
    """Harbor-environment interface backed by real local shell processes (no container)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.commands: list[str] = []

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.commands.append(command)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd or str(self.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec or 30)
        return SimpleNamespace(
            return_code=proc.returncode,
            stdout=out.decode(errors="replace"),
            stderr=err.decode(errors="replace"),
        )

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        shutil.copyfile(source_path, target_path)

    async def download_file(self, source_path: str, target_path: Any) -> None:
        if not Path(source_path).exists():
            raise FileNotFoundError(source_path)
        shutil.copyfile(source_path, target_path)


def chunk(
    content: str = "",
    reasoning: str = "",
    tool_calls: list | None = None,
    finish: str | None = None,
    usage: dict | None = None,
) -> Any:
    delta = SimpleNamespace(
        content=content or None,
        reasoning_content=reasoning or None,
        tool_calls=tool_calls,
        model_extra={},
    )
    choices = (
        [SimpleNamespace(delta=delta, finish_reason=finish)]
        if (content or reasoning or tool_calls or finish)
        else []
    )
    return SimpleNamespace(
        choices=choices,
        usage=SimpleNamespace(model_dump=lambda: usage) if usage else None,
    )


def tool_chunk(name: str, args: dict, index: int = 0, call_id: str = "c1") -> Any:
    tc = SimpleNamespace(
        index=index,
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )
    return chunk(tool_calls=[tc])


class _Stream:
    def __init__(self, chunks: list) -> None:
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


class ScriptedClient:
    """``client.chat.completions.create`` returning scripted streams or raising scripted errors."""

    def __init__(self, script: list, text_script: list | None = None) -> None:
        self.script = list(script)
        self.text_script = list(
            text_script or []
        )  # served to plain-text calls (no tools), when given
        self.requests: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any):
        self.requests.append(kwargs)
        item = (
            self.text_script.pop(0)
            if self.text_script and "tools" not in kwargs
            else self.script.pop(0)
        )
        if isinstance(item, Exception):
            raise item
        return _Stream(item)


def call(
    name: str, args: dict, call_id: str = "c1", reasoning: str = "thinking"
) -> list:
    """One model turn that makes a single tool call."""
    return [
        chunk(reasoning=reasoning),
        tool_chunk(name, args, call_id=call_id),
        chunk(finish="tool_calls"),
        chunk(
            usage={
                "prompt_tokens": 1000,
                "completion_tokens": 50,
                "prompt_tokens_details": {"cached_tokens": 200},
                "completion_tokens_details": {"reasoning_tokens": 20},
            }
        ),
    ]


class StatusError(Exception):
    def __init__(
        self, status: int, message: str = "err", headers: dict | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})
