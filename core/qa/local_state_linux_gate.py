"""One owned local-VM gate for the sealed provider-free state diagnostic."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

PROFILE = "codex-core-state-qual-20261102"
WORK = Path("/private/tmp/codex-core-state-retry-v0gNsFjH")
OUT = Path(__file__).resolve().parent / "evidence" / "state_linux_2b4cdad7_retry1"
ARCHIVE_SHA = "f8a86d2b48c51a85e599ccd8d12b90801dee3737ed02a368c0a71e866c8b357d"
REQ_SHA = "1fec19e0250fcc5e54cdde0700cc29a34004e1eb267d36b29d9e294177bad427"
IMAGE = "python@sha256:b224e2fe306f9d303251ada22961635e5b52a69c0414a0050611be31c59f5f5b"
BUILDER, TESTER, BUILT_IMAGE = "codex-state-build-2b4cdad7", "codex-state-test-2b4cdad7", "codex-state:2b4cdad7"

TEST_SCRIPT = r'''set +e
mkdir -p /evidence
cd /work/aether-core || exit 70
export PYTHONPATH=/work/aether-core/src:/work/aether-core
python -m pytest -q -p no:cacheprovider tests/test_facts_probe.py tests/test_facts_workspace.py \
  tests/test_facts_state.py tests/test_core_facts_loop.py tests/test_core_repl_keep.py > /evidence/pytest.log 2>&1
tests_rc=$?
python -m qa.evals.provided_state.run --evidence /evidence/good > /evidence/good.log 2>&1
good_rc=$?
python - > /evidence/knownbad.log 2>&1 <<'PY'
import sys
from qa.evals.provided_state import run
async def unavailable(*args, **kwargs):
    return {"ok": False, "reason": "synthetic observer unavailable"}
run.facts_probe.probe = unavailable
sys.argv = ["run", "--evidence", "/evidence/knownbad"]
run.main()
PY
bad_rc=$?
python - "$tests_rc" "$good_rc" "$bad_rc" > /evidence/verdict.json <<'PY'
import json, sys
from pathlib import Path
t, g, b = map(int, sys.argv[1:])
def read(path):
    try: return json.loads(Path(path).read_text())
    except (OSError, ValueError): return {}
good, bad = read('/evidence/good/summary.json'), read('/evidence/knownbad/summary.json')
ok = (t == 0 and g == 0 and b != 0 and good.get('artifact_controls_pass') is True
      and good.get('sensor_pass_count') == 5 and bad.get('artifact_controls_pass') is True
      and bad.get('sensor_pass_count', 5) < 5)
print(json.dumps({'tests_exit':t, 'good_exit':g, 'knownbad_exit':b, 'good_sensor_passes':good.get('sensor_pass_count'),
                  'knownbad_sensor_passes':bad.get('sensor_pass_count'), 'ok':ok}, indent=2))
sys.exit(0 if ok else 1)
PY
exit $?
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if digest(WORK / "source.tar.gz") != ARCHIVE_SHA or digest(WORK / "requirements.txt") != REQ_SHA:
        raise SystemExit("sealed input hash mismatch")
    OUT.mkdir(parents=True, exist_ok=False)
    docker_config = WORK / "docker-config"
    docker_config.mkdir(mode=0o700, exist_ok=False)
    env = {name: os.environ[name] for name in ("HOME", "USER", "LOGNAME", "TMPDIR", "LANG") if name in os.environ}
    env.update(PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", DOCKER_CONFIG=str(docker_config))
    records: list[dict] = []
    started_here = False
    tester_created = False
    outcome = "incomplete"

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)

    def command(label: str, argv: list[str], *, timeout: float, docker: bool = False, required: bool = True) -> str:
        cmd_env = dict(env)
        if docker:
            cmd_env["DOCKER_HOST"] = f"unix://{Path(env['HOME']) / '.colima' / PROFILE / 'docker.sock'}"
        started = time.monotonic()
        print(label, flush=True)
        try:
            result = subprocess.run(argv, env=cmd_env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=max(1.0, timeout))
            output, rc = result.stdout, result.returncode
        except subprocess.TimeoutExpired:
            records.append({"step": label, "status": "timeout", "seconds": round(time.monotonic() - started, 2)})
            raise RuntimeError(f"{label} timed out")
        (WORK / f"{len(records):02d}-{label}.log").write_text(output)
        records.append({"step": label, "exit": rc, "seconds": round(time.monotonic() - started, 2)})
        if required and rc:
            raise RuntimeError(f"{label} exited {rc}")
        return output

    def profiles() -> set[str]:
        result = subprocess.run(["colima", "list", "--json"], env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=15, check=True)
        return {json.loads(line)["name"] for line in result.stdout.splitlines() if line.strip()}

    try:
        if PROFILE in profiles():
            raise RuntimeError("refusing an existing profile")
        started_here = True
        setup_deadline = time.monotonic() + 300
        left = lambda: setup_deadline - time.monotonic()
        command("start", ["colima", "start", "--profile", PROFILE, "--cpus", "1", "--memory", "1",
                          "--disk", "4", "--root-disk", "5", "--runtime", "docker", "--mount", "none",
                          "--activate=false", "--ssh-config=false", "--ssh-agent=false", "--template=false"],
                timeout=left())
        command("pull", ["docker", "pull", "--platform", "linux/arm64", IMAGE], timeout=left(), docker=True)
        image_identity = command("image-identity", ["docker", "image", "inspect", "--format",
                                 "{{.Os}}/{{.Architecture}} {{.Id}}", IMAGE], timeout=left(), docker=True).strip()
        if not image_identity.startswith("linux/arm64 sha256:"):
            raise RuntimeError("unexpected image platform")
        records.append({"image_identity": image_identity})
        command("create-builder", ["docker", "run", "-d", "--name", BUILDER, "--entrypoint", "sh", IMAGE,
                                   "-c", "sleep 600"], timeout=left(), docker=True)
        runtime = command("runtime", ["docker", "exec", BUILDER, "uname", "-srm"],
                          timeout=left(), docker=True).strip()
        if not runtime.startswith("Linux "):
            raise RuntimeError("unexpected container kernel")
        records.append({"runtime": runtime})
        for filename in ("source.tar.gz", "requirements.txt"):
            command("copy-" + filename, ["docker", "cp", str(WORK / filename), f"{BUILDER}:/tmp/{filename}"],
                    timeout=left(), docker=True)
        setup = (f"echo '{ARCHIVE_SHA}  /tmp/source.tar.gz' | sha256sum -c - && "
                 f"echo '{REQ_SHA}  /tmp/requirements.txt' | sha256sum -c - && "
                 "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq procps && "
                 "PIP_CONFIG_FILE=/dev/null python -m pip install --no-input --no-cache-dir "
                 "--index-url https://pypi.org/simple -r /tmp/requirements.txt && "
                 "mkdir -p /work && tar -xzf /tmp/source.tar.gz -C /work && "
                 "python -m pip freeze > /work/python-versions.txt && dpkg-query -W procps > /work/os-versions.txt")
        command("install", ["docker", "exec", BUILDER, "sh", "-c", setup], timeout=left(), docker=True)
        command("commit-image", ["docker", "commit", BUILDER, BUILT_IMAGE], timeout=left(), docker=True)
        command("create-test", ["docker", "create", "--name", TESTER, "--network", "none",
                                "--entrypoint", "sh", BUILT_IMAGE, "-c", TEST_SCRIPT],
                timeout=left(), docker=True)
        tester_created = True
        isolation = command("inspect-isolation", ["docker", "inspect", "--format",
                            "{{.HostConfig.NetworkMode}} {{len .Mounts}}", TESTER], timeout=left(), docker=True).strip()
        if isolation != "none 0":
            raise RuntimeError("test container is not isolated")
        command("test", ["docker", "start", "-a", TESTER], timeout=300, docker=True)
        outcome = "passed"
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, KeyboardInterrupt) as exc:
        outcome = "incomplete_or_failed"
        records.append({"error_type": type(exc).__name__, "message": str(exc)[:200]})
    finally:
        if tester_created:
            for label, source, target, timeout in (
                ("copy-evidence", f"{TESTER}:/evidence", str(OUT / "container"), 45),
                ("copy-versions", f"{TESTER}:/work/python-versions.txt", str(OUT), 20),
                ("copy-os-versions", f"{TESTER}:/work/os-versions.txt", str(OUT), 20),
            ):
                try:
                    command(label, ["docker", "cp", source, target], timeout=timeout, docker=True)
                except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    outcome = "incomplete_or_failed"
                    records.append({"copy_error": label, "error_type": type(exc).__name__})
        if started_here:
            try:
                command("stop-owned-profile", ["colima", "stop", "--profile", PROFILE, "--force"],
                        timeout=60, required=False)
                command("delete-owned-profile", ["colima", "delete", "--profile", PROFILE, "--force", "--data"],
                        timeout=60, required=False)
                if PROFILE in profiles():
                    outcome = "incomplete_or_failed"
                    records.append({"cleanup": "owned profile still present"})
                else:
                    records.append({"cleanup": "owned profile absent"})
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                outcome = "incomplete_or_failed"
                records.append({"cleanup_error": type(exc).__name__})
        (OUT / "host-summary.json").write_text(json.dumps({"outcome": outcome, "records": records}, indent=2) + "\n")
        print("state gate:", outcome, flush=True)
    return 0 if outcome == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
