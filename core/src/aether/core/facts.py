"""One Core-owned information channel for bounded environment observations."""

from __future__ import annotations

from copy import deepcopy
import json
import posixpath
import re
import time
from typing import Any, Callable

from . import facts_probe
from .env import Environment

_MUTATING_TOOLS = frozenset({"terminal", "python", "write_file", "edit_file"})
_FULL_REFRESH = re.compile(
    r"\b(?:apt(?:-get)?|apk|dnf|yum|conda|pip3?|npm|cargo|install|"
    r"chmod|ln|curl|wget|source|export|make)\b|\bPATH\s*=", re.I,
)


def _shown(value: str | None) -> str:
    return "not resolved" if value is None else json.dumps(value, ensure_ascii=True)


class Facts:
    """Observed fields and their age; unobserved world state remains unknown."""

    def __init__(self, env: Environment, workdir: str, remaining: Callable[[], float],
                 trace: Callable[..., None], *, terminal_state: Callable[[str], dict | None] | None = None,
                 hosts: tuple[tuple[str, int], ...] | None = None):
        self.env, self.workdir, self.remaining, self.trace = env, workdir, remaining, trace
        self.terminal_state = terminal_state
        self.hosts = facts_probe.HOSTS if hosts is None else hosts
        self.snapshot: dict[str, Any] | None = None
        self.shared_known = False
        self.last_shared_step: int | None = None
        self.last_full_step: int | None = None
        self.terminal_paths: dict[str, dict[str, bool] | None] = {}
        self.probes = 0
        self.probe_seconds = 0.0
        self.last_finish_change: str | None = None

    async def _observe(self, step: int, *, full: bool) -> dict[str, Any]:
        started = time.monotonic()
        result = await facts_probe.probe(
            self.env, self.workdir, full=full, remaining_s=self.remaining(), hosts=self.hosts,
        )
        elapsed = time.monotonic() - started
        self.probes += 1
        self.probe_seconds += elapsed
        self.trace("core_facts_probe", step=step, full=full, ok=result["ok"],
                   duration_s=round(elapsed, 3))
        return result

    async def start(self) -> str:
        result = await self._observe(0, full=True)
        if not result["ok"]:
            self.shared_known = False
            return "[core facts]\nShared probe at step 0: unmeasured."
        self.snapshot = result["facts"]
        self.shared_known = True
        self.last_shared_step = self.last_full_step = 0
        return self._initial(self.snapshot, 0)

    def _initial(self, facts: dict[str, Any], step: int) -> str:
        commands = facts["commands"]
        available = [f"{name}={_shown(path)}" for name, path in commands.items() if path is not None]
        missing = [name for name, path in commands.items() if path is None]
        versions = [f"{name}={version or 'unmeasured'}" for name, version in (facts["versions"] or {}).items()]
        managers = [name for name in facts_probe.MANAGERS if commands.get(name) is not None]
        network = [f"{host}={state}" for host, state in (facts["network"] or {}).items()]
        memory = facts["host_available_memory_kib"]
        lines = [
            "[core facts]",
            f"Shared probe PATH at step {step}: " + (", ".join(available) or "no listed commands resolved") + ".",
            "Names not resolved on that PATH: " + (", ".join(missing) or "none") + ".",
            "Package-manager names resolved: " + (", ".join(managers) or "none") + ".",
            f"Version output at step {step}: " + (", ".join(versions) or "unmeasured") + ".",
            f"Permitted non-hidden working-directory entries at step {step}: " +
            (", ".join(facts["files"]) or "none observed") +
            ("; incomplete." if not facts["files_complete"] else "."),
            f"TCP probes at step {step}: " + (", ".join(network) or "unmeasured") + ".",
            f"Kernel-reported host available memory at step {step}: " +
            (f"{memory} KiB." if memory is not None else "unmeasured."),
            "Scope: shared probe shell; terminal PATHs, package contents, program behavior, "
            "container memory limits, excluded entries and later changes are unobserved.",
        ]
        return "\n".join(lines)

    def _terminal_delta(self, step: int, name: str) -> list[str]:
        if self.terminal_state is None:
            return []
        observed = self.terminal_state(name)
        lookup = observed.get("command_resolution") if isinstance(observed, dict) else None
        had_observation = name in self.terminal_paths
        prior = self.terminal_paths.get(name)
        if not isinstance(lookup, dict) or lookup.get("status") != "observed":
            self.terminal_paths[name] = None
            return [f"Terminal {json.dumps(name)} PATH at step {step}: unmeasured."] if prior is not None else []
        current = lookup.get("resolved")
        if not isinstance(current, dict) or any(type(v) is not bool for v in current.values()):
            self.terminal_paths[name] = None
            return [f"Terminal {json.dumps(name)} PATH at step {step}: unmeasured."] if prior is not None else []
        self.terminal_paths[name] = dict(current)
        if prior is None and self.snapshot:
            previous = {key: self.snapshot["commands"].get(key) is not None for key in current}
        else:
            previous = prior or {}
        changes = [f"{key}={'resolved' if value else 'not resolved'}" for key, value in current.items()
                   if key in previous and previous[key] != value]
        if had_observation and prior is None:
            resolved = [key for key, value in current.items() if value]
            missing = [key for key, value in current.items() if not value]
            return [f"Terminal {json.dumps(name)} PATH observed again at step {step}: "
                    f"resolved {', '.join(resolved) or 'none'}; not resolved {', '.join(missing) or 'none'}."]
        return ([f"Terminal {json.dumps(name)} PATH observed at step {step}: " + ", ".join(changes) + "."]
                if changes else [])

    async def after_action(self, step: int, tool: str, args: dict, result: str) -> str:
        updates = self._terminal_delta(step, str(args.get("name") or "main")) if tool == "terminal" else []
        if tool not in _MUTATING_TOOLS and tool != "finish" and step % 10:
            return "[core facts]\n" + "\n".join(updates) if updates else ""
        command = str(args.get("input") or args.get("code") or "")
        full = tool != "finish" and (self.snapshot is None or step % 10 == 0 or bool(_FULL_REFRESH.search(command)))
        observation = await self._observe(step, full=full)
        if not observation["ok"]:
            if self.shared_known:
                updates.append(f"Shared probe at step {step}: unmeasured; last observed at step {self.last_shared_step}.")
            self.shared_known = False
        else:
            current = observation["facts"]
            old = self.snapshot
            if old is None:
                updates.extend(self._initial(current, step).splitlines()[1:])
            elif not self.shared_known:
                updates.append(f"Shared probe at step {step}: observed again.")
            if old is not None:
                completed = ((tool == "write_file" and result.startswith("wrote ")) or
                             (tool == "edit_file" and result.startswith("edited ")))
                authored = self._authored_top_level(tool, args) if completed else None
                updates.extend(self._changes(old, current, step, full, authored))
                if not full:
                    for key in ("versions", "network"):
                        current[key] = old[key]
                current["host_available_memory_kib"] = old["host_available_memory_kib"]
            self.snapshot = current
            self.shared_known = True
            self.last_shared_step = step
            if full:
                self.last_full_step = step
        if tool == "finish":
            self.last_finish_change = "\n".join(updates) or None
            return ""
        return "[core facts]\n" + "\n".join(updates) if updates else ""

    def _authored_top_level(self, tool: str, args: dict) -> str | None:
        if tool not in ("write_file", "edit_file") or not isinstance(args.get("path"), str):
            return None
        path = args["path"]
        if ".." in path.split("/"):
            return None
        root = posixpath.normpath(self.workdir)
        absolute = posixpath.normpath(path if path.startswith("/") else posixpath.join(root, path))
        return posixpath.basename(absolute) if posixpath.dirname(absolute) == root else None

    @staticmethod
    def _changes(old: dict, current: dict, step: int, full: bool, authored: str | None) -> list[str]:
        updates = []
        for name, value in current["commands"].items():
            if old["commands"].get(name) != value:
                updates.append(f"Shared PATH at step {step}: {name}={_shown(value)}.")
        if (old["files"], old["files_complete"]) != (current["files"], current["files_complete"]):
            if old["files_complete"] and current["files_complete"]:
                added = sorted(set(current["files"]) - set(old["files"]) - {authored})
                removed = sorted(set(old["files"]) - set(current["files"]))
                detail = "; ".join(x for x in (
                    "added " + ", ".join(added) if added else "",
                    "removed " + ", ".join(removed) if removed else "",
                ) if x)
                if detail:
                    updates.append(f"Permitted non-hidden working-directory entries at step {step}: {detail}.")
            else:
                updates.append(f"Permitted non-hidden working-directory entry sample changed at step {step}; "
                               "coverage incomplete or changed.")
        if full:
            for name, value in current["versions"].items():
                if (old["versions"] or {}).get(name) != value:
                    updates.append(f"Version output at step {step}: {name}={value or 'unmeasured'}.")
            for host, value in current["network"].items():
                if (old["network"] or {}).get(host) != value:
                    updates.append(f"TCP probe at step {step}: {host}={value}.")
        return updates

    def record(self) -> dict[str, Any]:
        return {"shared_known": self.shared_known, "last_shared_step": self.last_shared_step,
                "last_full_step": self.last_full_step, "snapshot": deepcopy(self.snapshot),
                "terminal_paths": deepcopy(self.terminal_paths), "probe_count": self.probes,
                "probe_seconds": self.probe_seconds, "finish_observations_not_shown": self.last_finish_change,
                "scope": "bounded observations; package contents, hidden entries and external state unobserved"}
