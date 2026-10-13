"""Exercise the installed adapter through real Harbor + Docker + SDK + an independent grader.

The HTTP server supplies explicitly scripted responses. No GLM/the reviewer/provider call is made.
Requires the Harbor extra, Linux Docker, and an already available image with bash, Python, and script.
"""

import argparse
import asyncio
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import uuid

from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    TrialConfig,
)
from harbor.trial.trial import Trial


def response(name, arguments, identity):
    raw = json.dumps(arguments)
    split = max(1, len(raw) // 2)
    deltas = [
        (
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": identity,
                        "type": "function",
                        "function": {"name": name, "arguments": raw[:split]},
                    }
                ]
            },
            None,
        ),
        ({"tool_calls": [{"index": 0, "function": {"arguments": raw[split:]}}]}, None),
        ({}, "tool_calls"),
    ]
    chunks = [
        {
            "id": identity,
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "engineering-fixture",
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        }
        for delta, finish in deltas
    ]
    return (
        "".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n"
    ).encode()


async def run_case(root, image, mode, bad):
    nonce = "fixture-" + uuid.uuid4().hex
    name = mode + ("-known-bad" if bad else "-known-good")
    task = root / name
    (task / "environment").mkdir(parents=True)
    (task / "tests").mkdir()
    (task / "instruction.md").write_text(
        f"Write exactly {nonce} followed by a newline to /app/output.txt.\n"
    )
    (task / "task.toml").write_text(f'''version = "1.0"
[agent]
timeout_sec = 60
[verifier]
timeout_sec = 20
[environment]
docker_image = "{image}"
cpus = 2
memory_mb = 1024
''')
    (task / "tests/expected.txt").write_text(nonce + "\n")
    (task / "tests/test.sh").write_text("""#!/bin/bash
mkdir -p /logs/verifier
if cmp -s /app/output.txt /tests/expected.txt && [ ! -e /app/credential_leak ]; then
  printf '1\\n' > /logs/verifier/reward.txt
else
  printf '0\\n' > /logs/verifier/reward.txt
fi
""")
    (task / "tests/test.sh").chmod(0o755)
    script = deque(
        [
            (
                "terminal",
                {
                    "input": 'mkdir -p /app; if [ -n "$AETHER_FW_GLM_53_FLASH_KEY" ] || [ -n "$external-evaluator_API_KEY" ]; then touch /app/credential_leak; fi'
                },
            ),
            ("python", {"code": "x=41; print(x+1)"}),
            (
                "write_file",
                {
                    "path": "/app/output.txt",
                    "content": ("wrong" if bad else nonce) + "\n",
                },
            ),
            ("read_file", {"path": "/app/output.txt"}),
            (
                "terminal",
                {
                    "input": "printf 'P3\\n2 1\\n255\\n255 0 0 0 0 255\\n' > /app/picture.ppm"
                },
            ),
            ("view_image", {"path": "/app/picture.ppm"}),
            ("finish", {"summary": "scripted engineering fixture finished"}),
        ]
    )
    captured = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            captured.append(body)
            tool, arguments = script.popleft()
            encoded = response(tool, arguments, "fixture-call-" + str(len(captured)))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    try:
        env = {
            "AETHER_CORE_REVIEW": "off",
            "AETHER_AGENT_DEADLINE_SEC": "60",
            "AETHER_CORE_CONTEXT": mode,
            "AETHER_CORE_REPL": "on",
            "AETHER_CORE_IMAGES": "on",
            "AETHER_FW_GLM_53_FLASH_ENDPOINT": f"http://127.0.0.1:{http.server_port}",
            "AETHER_FW_GLM_53_FLASH_KEY": "fixture-host-only-key",
            "external-evaluator_API_KEY": "fixture-host-only-reviewer",
            "AETHER_FW_GLM_53_FLASH_DEPLOYMENT": "engineering-fixture",
        }
        config = TrialConfig(
            task=TaskConfig(path=task),
            trial_name=name,
            trials_dir=root / "trials",
            agent=AgentConfig(
                import_path="aether.core.harbor_agent:AetherCoreAgent",
                override_timeout_sec=60,
                env=env,
            ),
            environment=EnvironmentConfig(type="docker", delete=True),
        )
        trial = await Trial.create(config)
        result = await trial.run()
        payload = result.model_dump(mode="json")
        (root / (name + "-result.json")).write_text(json.dumps(payload, indent=2))
        (root / (name + "-requests.json")).write_text(json.dumps(captured, indent=2))
        rewards = result.verifier_result.rewards if result.verifier_result else None
        expected = 0.0 if bad else 1.0
        assert result.exception_info is None, payload.get("exception_info")
        assert rewards and list(rewards.values()) == [expected], rewards
        assert len(captured) == 7 and not script
        logs = root / "trials" / name / "agent"
        record = json.loads((logs / "aether_run_record.json").read_text())
        trace = [
            json.loads(line)
            for line in (logs / "core_trace.jsonl").read_text().splitlines()
        ]
        assert (
            record["status"] == "finished"
            and record["run_metrics"]["provider_input_tokens"] is None
        )
        assert any(
            r["event"] == "tool" and r["name"] == "python" and "42" in r["result"]
            for r in trace
        )
        assert any(isinstance(m.get("content"), list) for m in captured[-1]["messages"])
        from aether.core.calls import requests

        assert [
            row["request"] for row in requests(logs / "core_calls.jsonl")
        ] == captured
        assert "fixture-host-only-key" not in (logs / "core_calls.jsonl").read_text()
        return {
            "case": name,
            "reward": expected,
            "http_requests": len(captured),
            "real_model_calls": 0,
            "harbor_exception": None,
            "unknown_usage_preserved": True,
        }
    finally:
        http.shutdown()
        http.server_close()
        worker.join()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for mode, bad in [("project", False), ("clm", True)]:
        rows.append(await run_case(args.out, args.image, mode, bad))
    (args.out / "SUMMARY.json").write_text(
        json.dumps({"rows": rows, "real_model_calls": 0}, indent=2)
    )
    print(json.dumps(rows))


if __name__ == "__main__":
    asyncio.run(main())
