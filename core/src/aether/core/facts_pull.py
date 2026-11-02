"""Shell-readable, opt-in presentation of Core's bounded state observations."""

from __future__ import annotations

import json
import posixpath
import shlex
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from . import facts_probe
from . import facts_replay
from .env import run
from .facts import Facts
from .facts_workspace import ManagedFactsText


_WRITE = r"""
import json, os, re, subprocess, sys, uuid
control, payload, workdir = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]
start_head, step, expected_root = sys.argv[4], int(sys.argv[5]), json.loads(sys.argv[6])
def open_dir(path):
    parts = [x for x in path.split('/') if x]
    if not path.startswith('/') or not parts or any(x in ('.', '..') for x in parts):
        raise ValueError('unsafe control directory')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = child
        return fd
    except Exception:
        os.close(fd); raise
def git_state():
    git = next((p for p in ('/usr/bin/git', '/bin/git', '/usr/local/bin/git')
                if os.path.isfile(p) and os.access(p, os.X_OK)), None)
    if git is None or expected_root is None:
        return None, None, 'unknown'
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_OPTIONAL_LOCKS': '0'}
    def call(*args):
        return subprocess.run([git, '-c', 'core.fsmonitor=false', '-C', workdir, *args],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              text=True, timeout=3, env=env)
    try:
        fd = open_dir(workdir)
        try:
            before = os.fstat(fd)
            if [before.st_dev, before.st_ino] != expected_root:
                return None, None, 'unknown'
            top = call('rev-parse', '--show-toplevel')
            head_result = call('rev-parse', '--verify', 'HEAD^{commit}')
            head = head_result.stdout.strip()
            if (top.returncode or os.path.realpath(top.stdout.strip()) != os.path.realpath(workdir)
                    or head_result.returncode or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', head)):
                return None, None, 'unknown'
            baseline = start_head if re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', start_head) else None
            if baseline is None and step == 0:
                baseline = head
            relation = 'unknown'
            if baseline is not None:
                result = call('merge-base', '--is-ancestor', baseline, head)
                relation = 'yes' if result.returncode == 0 else 'no' if result.returncode == 1 else 'unknown'
            check = open_dir(workdir)
            try:
                after = os.fstat(check)
                if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                    return None, None, 'unknown'
            finally: os.close(check)
            return baseline, head, relation
        finally: os.close(fd)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, None, 'unknown'
baseline, head, relation = git_state()
if head is None:
    payload['changes.txt'] += 'Git HEAD and ancestry: unknown.\n'
else:
    payload['changes.txt'] += 'Git HEAD observed at step %d: %s.\n' % (step, head)
    if baseline is None:
        payload['changes.txt'] += 'Git start commit: unknown.\n'
    else:
        payload['changes.txt'] += 'Git start commit observed before the first action: %s.\n' % baseline
        text = 'is an ancestor of' if relation == 'yes' else 'is not an ancestor of' if relation == 'no' else 'ancestry is unknown for'
        payload['changes.txt'] += 'The start commit %s the observed HEAD.\n' % text
root = open_dir(control)
try:
    try: os.mkdir('state', 0o700, dir_fd=root)
    except FileExistsError: pass
    directory = os.open('state', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
    try:
        for name in ('changes.txt', 'checks.txt', 'unobserved.txt'):
            temp = '.core-state-' + uuid.uuid4().hex
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
            try:
                data = payload[name].encode('utf-8')
                with os.fdopen(fd, 'wb') as out: out.write(data)
                os.replace(temp, name, src_dir_fd=directory, dst_dir_fd=directory)
            except Exception:
                try: os.unlink(temp, dir_fd=directory)
                except OSError: pass
                raise
        check_root = open_dir(control)
        try:
            check = os.open('state', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=check_root)
            try:
                a, b = os.fstat(directory), os.fstat(check)
                if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                    raise ValueError('state directory changed during publication')
            finally: os.close(check)
        finally: os.close(check_root)
    finally: os.close(directory)
finally: os.close(root)
print(json.dumps({'start_head': baseline}))
"""


def make(env, workdir, remaining, trace, *, terminal_state, python_state, pull, control_dir):
    cls = PullFacts if pull else Facts
    extra = {"control_dir": control_dir} if pull else {}
    return cls(env, workdir, remaining, trace, terminal_state=terminal_state,
               python_state=python_state, **extra)


def trace_start_copy(service, row: dict, source: str, trace) -> None:
    trace("start_copy", **row)
    if isinstance(service, PullFacts):
        service.start_copy = {"status": "created" if row.get("copied") else "not_created", "source": source}
        if row.get("copied") and isinstance(row.get("path"), str):
            service.start_copy["path"] = row["path"]


def attach(clm: Any, messages: list, resumed: bool, service: "PullFacts") -> int:
    """Retain the private checkpoint without adding another note on a new run."""
    items = clm.pinned if clm else messages
    matches = [i for i, item in enumerate(items) if item.get("role") == "user"
               and isinstance(item.get("content"), ManagedFactsText)]
    if len(matches) > 1:
        raise ValueError("multiple Core-owned state notes")
    if matches:
        index = matches[0]
        content = str(items[index]["content"])
        if content.startswith("[core facts]\n"):
            content = service.note
    elif resumed:
        index = len(items)
        items.append({"role": "user", "content": service.note})
        content = service.note
    else:
        index = 1
        content = str(items[index]["content"])
    items[index] = {"role": "user", "content": ManagedFactsText(content, service.initial_workspace)}
    if clm:
        clm._managed_facts_pin_index = index
    return index


def _metadata_changed(before: dict | None, after: dict | None) -> bool | None:
    if before is None or after is None or before["root"] != after["root"]:
        return None
    old, new = before["files"], after["files"]
    if any(old[path] != new[path] for path in old.keys() & new.keys()):
        return True
    if before["complete"] and after["complete"]:
        return old.keys() != new.keys()
    return None


class PullFacts(Facts):
    def __init__(self, *args, control_dir: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.control_dir = control_dir
        state = posixpath.join(control_dir, "state")
        self.note = f"(Core state directory: {state}; files: changes.txt, checks.txt, unobserved.txt.)"
        self.steps: list[dict[str, Any]] = []
        self.last_workspace: dict | None = None
        self.direct_reads: set[str] = set()
        self.start_copy: dict[str, Any] = {"status": "not_requested"}

    async def start(self) -> str:
        await super().start()
        self.last_workspace = self._current_workspace()
        published = await self._publish(0)
        default_cwd = None
        try:
            result = await run(self.env, "pwd -P", timeout_s=3)
            if result.code == 0 and len(result.stdout.splitlines()) == 1:
                default_cwd = result.stdout.strip()
        except Exception:
            pass
        copy = dict(self.start_copy)
        copy["source_git_head"] = getattr(self.initial_workspace, "git_start", None)
        copy["identity_scope"] = "source HEAD only; copied bytes and dirty files were not hashed"
        self._durable("core_state_start", start_copy=copy,
                      default_exec_cwd=facts_replay.cwd_fact(default_cwd, self.workdir),
                      image_workdir={"status": "unknown", "reason": "image metadata unavailable to Core"})
        return self.note if published else ""

    async def after_action(self, step, tool, args, result, *, call_id=None) -> str:
        previous_python = deepcopy(self.python_session)
        await super().after_action(step, tool, args, result, call_id=call_id)
        if tool == "read_file" and isinstance(args.get("path"), str) and not result.startswith("error:"):
            path = args["path"]
            absolute = posixpath.normpath(path if path.startswith("/") else posixpath.join(self.workdir, path))
            prefix = posixpath.normpath(self.workdir).rstrip("/") + "/"
            relative = absolute.removeprefix(prefix) if absolute.startswith(prefix) else ""
            if facts_probe.safe_relative(relative):
                self.direct_reads.add(relative)
        current = self._current_workspace()
        changed = _metadata_changed(self.last_workspace, current)
        for row in self.steps:
            if changed is True and row["changed_after"] is None:
                row["changed_after"] = step
            elif changed is None:
                row["unknown_after"] = True
        if tool != "finish":
            self.steps.append({"step": step, "tool": tool, "observed_at": datetime.now(timezone.utc).isoformat(),
                               "changed_after": None, "unknown_after": current is None})
        self.last_workspace = current
        if tool in ("terminal", "python"):
            self._record_state_step(step, tool, args, previous_python)
        await self._publish(step)
        return ""

    def _durable(self, event: str, **data) -> None:
        writer = getattr(self.trace, "durable", None)
        if callable(writer):
            writer(event, **data)
        else:
            self.trace(event, durability="unconfirmed", **data)

    def _record_state_step(self, step: int, tool: str, args: dict, previous_python: dict | None) -> None:
        if tool == "terminal":
            name = str(args.get("name") or "main")
            state = self.terminal_state(name) if self.terminal_state else None
            before = state.get("pre_action_cwd") if isinstance(state, dict) else None
            after = (state.get("last_observed_cwd") if isinstance(state, dict)
                     and state.get("foreground") == "idle_at_last_observation"
                     and not state.get("cwd_uncertain") else None)
            mode = args.get("mode", "command")
            mode = mode if mode in ("command", "keys") else "unknown"
            old_names = state.get("pre_action_env_names") if isinstance(state, dict) else None
            new_names = (state.get("env_names") if isinstance(state, dict)
                         and state.get("foreground") == "idle_at_last_observation"
                         and not state.get("cwd_uncertain") else None)
        else:
            before = (previous_python.get("last_observed_cwd") if isinstance(previous_python, dict)
                      and previous_python.get("foreground") == "idle_at_last_observation" else None)
            after = (self.python_session.get("last_observed_cwd") if isinstance(self.python_session, dict)
                     and self.python_session.get("foreground") == "idle_at_last_observation" else None)
            mode = "python"
            old_names = new_names = None
        if isinstance(old_names, list) and isinstance(new_names, list):
            environment = {"status": "names_observed", "added": sorted(set(new_names) - set(old_names)),
                           "removed": sorted(set(old_names) - set(new_names)), "values": "not recorded",
                           "scope": "filtered exported names; changes to values and excluded names are unknown"}
        else:
            environment = {"status": "unknown", "reason": "exported names or values were not observed"}
        self._durable("core_state_step", step=step, tool=tool, mode=mode,
                      pre_cwd=facts_replay.cwd_fact(before, self.workdir),
                      post_cwd=facts_replay.cwd_fact(after, self.workdir),
                      environment_delta=environment)

    def _current_workspace(self) -> dict | None:
        if not self.shared_known or not self.snapshot:
            return None
        return deepcopy(self.snapshot.get("workspace"))

    async def _publish(self, step: int) -> bool:
        changes = [f"Last publication after Core step {step}. Bounded workspace metadata observations; "
                   "file contents and excluded paths are not established."]
        if self.initial_workspace.initial is None:
            changes.append("Initial workspace observation: unknown.")
        changes.extend(self.initial_workspace.describe(row) for row in self.initial_workspace.changes.values())
        initial, current = self.initial_workspace.initial, self._current_workspace()
        if initial is not None and current is not None and initial["root"] == current["root"]:
            for path in sorted(current["files"].keys() - initial["files"].keys()):
                changes.append(f"At step {step}, {json.dumps(path)} was in the current sample but not the initial sample.")
        else:
            changes.append("Current comparison with the initial workspace observation: unknown.")
        if len(changes) == 1:
            changes.append("No initial-workspace metadata differences have been observed.")
        checks = ["Tool steps and later bounded workspace metadata observations; times are Core host observations."]
        for row in self.steps:
            if row["changed_after"] is not None:
                later = f"metadata difference observed after this step at step {row['changed_after']}"
            elif row["unknown_after"]:
                later = "later workspace observations incomplete or unavailable"
            else:
                later = "no later difference observed in the bounded samples"
            checks.append(f"step {row['step']} {row['tool']} at {row['observed_at']}: {later}.")
        checks.append("A matching sample does not prove no files changed or that a check was sufficient.")
        unobserved = ["File opens by shell, Python and background processes are not observed; unopened files are unknown."]
        initial = self.initial_workspace.initial
        if initial is None:
            unobserved.append("Initial eligible workspace files are unknown.")
        else:
            remaining = sorted(set(initial["files"]) - self.direct_reads)
            unobserved.append("Initial eligible paths without a successful direct read_file receipt: " +
                              (", ".join(remaining) if remaining else "none in the observed sample") + ".")
            if not initial["complete"]:
                unobserved.append("The initial workspace sample was incomplete.")
        payload = {
            "changes.txt": "\n".join(changes) + "\n",
            "checks.txt": "\n".join(checks) + "\n",
            "unobserved.txt": "\n".join(unobserved) + "\n",
        }
        lines = [f"__af_root={shlex.quote(self.workdir)}"]
        lines += facts_probe._system_binary("__af_python", facts_probe.SYSTEM_PYTHON_PATHS)
        workspace = self._current_workspace()
        root = workspace["root"] if workspace is not None else None
        baseline = getattr(self.initial_workspace, "git_start", None) or "-"
        initial_step = 0 if step == 0 and not self.initial_workspace.continuations else max(1, step)
        lines += ['[ -n "$__af_python" ] || exit 1',
                  f'"$__af_python" -I -S -B -c {shlex.quote(_WRITE)} '
                  f'{shlex.quote(self.control_dir)} {shlex.quote(json.dumps(payload))} '
                  f'{shlex.quote(self.workdir)} {shlex.quote(baseline)} {initial_step} {shlex.quote(json.dumps(root))}']
        try:
            if self.remaining() < 2:
                return False
            result = await run(self.env, "\n".join(lines), timeout_s=max(1, min(10, int(self.remaining() - 1))))
            ok = result.code == 0
            if ok:
                captured = json.loads(result.stdout).get("start_head")
                if isinstance(captured, str) and len(captured) in (40, 64):
                    self.initial_workspace.git_start = captured
        except Exception:
            ok = False
        self.trace("core_facts_pull_publish", step=step, ok=ok)
        return ok
