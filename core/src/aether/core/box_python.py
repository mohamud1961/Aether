"""A python3 for the differential check's box when the task image has none (AETHER_CORE_BOX_PYTHON).

Why (31 Oct, live diffcheck runs with Luna): the check and its harness-side manifest run on python3, and many task
images ship without it. 4 of 11 runs lost the check that way (3 skipped at start, 1 failed 19 times), so the
mechanism dropped out on exactly the bare images it was meant to cover. The box is the check's own no-network copy
of the container, so the harness can install a relocatable CPython there (a python-build-standalone "install_only"
tarball on the host, copied in with docker cp) without touching the solver's environment.
"""

from __future__ import annotations

import os
import shlex

from .env import Environment, run

BOX_PYTHON_ENV = "AETHER_CORE_BOX_PYTHON"  # host path of the tarball; empty: no install, the check is skipped
ROOT = "/opt/aether-python"
STAGE = "/tmp/.aether-python.tar.gz"


REPL_PYTHON_ENV = "AETHER_CORE_REPL_PYTHON"  # host path of the same tarball for the REPL; empty (default): no install
REPL_ROOT = "/tmp/.aether/python"  # outside PATH: the task's own environment keeps having no python3


async def install(env: Environment, tarball: str, root: str) -> tuple[str, str]:
    """(interpreter path, version) after unpacking the relocatable CPython at root; ("", why) when it cannot."""
    q = shlex.quote
    probe = f"{q(root)}/bin/python3 -c 'import sys; print(\"%d.%d.%d\" % sys.version_info[:3])'"
    present = await run(env, probe, timeout_s=30)  # an earlier controller's install is reused, never overwritten
    if present.code == 0 and present.stdout.strip():
        return f"{root}/bin/python3", present.stdout.strip()
    if not os.path.isfile(tarball):
        return "", f"relocatable python missing on the host ({tarball})"
    upload = getattr(env, "upload_file", None)
    if upload is None:
        return "", "the container cannot receive files"
    try:
        await upload(tarball, STAGE)
    except Exception as exc:  # reported to the caller, which states it
        return "", f"copying python failed: {exc}"[:300]
    command = f"mkdir -p {q(root)} && tar -xzf {q(STAGE)} -C {q(root)} --strip-components=1 && rm -f {q(STAGE)} && {probe}"
    result = await run(env, command, timeout_s=180)
    if result.code != 0:
        return "", f"installing python failed: {(result.stderr or result.stdout)[-200:]}"
    return f"{root}/bin/python3", result.stdout.strip()


async def ensure(box: Environment, tarball: str) -> tuple[bool, str]:
    """(True, how) when python3 runs in the box, installing the harness's CPython if needed; else (False, why)."""
    if (await run(box, "command -v python3", timeout_s=30)).code == 0:
        return True, "task python3"
    if not tarball:
        return False, "no python3 in the task container"
    path, how = await install(box, tarball, ROOT)
    if not path:
        return False, f"no python3 in the task container; {how}"
    q = shlex.quote
    result = await run(box, f"mkdir -p /usr/local/bin && ln -sf {q(path)} /usr/local/bin/python3", timeout_s=30)
    if result.code != 0:
        return False, f"no python3 in the task container; linking python failed: {(result.stderr or result.stdout)[-200:]}"
    return True, f"harness python {how}"
