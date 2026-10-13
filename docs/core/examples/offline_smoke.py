"""Run a scripted provider through real tools. No network, model, or credential is used.

After installing the wheel: python examples/offline_smoke.py
"""
import asyncio
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace as N

from aether.core.calls import CallLog, requests
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider


class LocalSandbox:
    def __init__(self, root):
        self.root = root

    async def exec(self, command, cwd=None, env=None, timeout_sec=30):
        process = await asyncio.create_subprocess_shell(command, cwd=cwd or self.root,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(process.communicate(), timeout_sec)
        return N(return_code=process.returncode, stdout=out.decode(errors="replace"), stderr=err.decode(errors="replace"))

    async def upload_file(self, source_path, target_path):
        shutil.copyfile(source_path, target_path)

    async def download_file(self, source_path, target_path):
        shutil.copyfile(source_path, target_path)


class ScriptedProvider:
    def __init__(self):
        self.chat = N(completions=self)
        self.turns = iter([
            ("terminal", {"input": "printf 'hello from installed Aether\\n' > result.txt; cat result.txt"}),
            ("finish", {"summary": "The real file was written and read."})])

    async def create(self, **request):
        name, args = next(self.turns)
        async def stream():
            yield N(id="offline-smoke", choices=[N(finish_reason="tool_calls", delta=N(
                content=None, tool_calls=[N(index=0, id=name, function=N(name=name, arguments=json.dumps(args)))]))])
        return stream()


async def main():
    with tempfile.TemporaryDirectory(prefix="aether-smoke-") as folder:
        root = Path(folder)
        provider = ChatProvider(ScriptedProvider(), model="scripted-no-network", params={},
                                log=CallLog(root / "calls.jsonl"))
        result = await run_agent(env=LocalSandbox(root), task="Write a greeting to result.txt and read it.",
            workdir=str(root), provider=provider, timeout_s=60, trace=Trace(root / "trace.jsonl"),
            config=CoreConfig(control_dir=str(root / "control")))
        actual = (root / "result.txt").read_text()
        assert actual == "hello from installed Aether\n" and result.status == "finished"
        assert len(list(requests(root / "calls.jsonl"))) == 2
        print(json.dumps({"status": result.status, "actual_file": actual, "network_calls": 0,
                          "attempts": provider.log.totals()["all"]["attempts"]}))


if __name__ == "__main__":
    asyncio.run(main())
