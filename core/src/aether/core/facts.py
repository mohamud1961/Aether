"""One Core-owned information channel for bounded environment observations."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import posixpath
import re
import time
from typing import Any, Callable

from . import facts_probe
from .env import Environment
from .facts_workspace import InitialWorkspace, ManagedFactsText, install_project_note  # noqa: F401

_MUTATING_TOOLS = frozenset({"terminal", "python", "write_file", "edit_file"})
_FULL_REFRESH = re.compile(
    r"\b(?:apt(?:-get)?|apk|dnf|yum|conda|pip3?|npm|cargo|install|"
    r"chmod|ln|curl|wget|source|export|make)\b|\bPATH\s*=", re.I,
)
_MENTIONED_PATH = re.compile(
    r"(?<![A-Za-z0-9_./-])(?:\./)?"
    r"([A-Za-z0-9_][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_][A-Za-z0-9_.+-]*)*\.[A-Za-z0-9_+-]+)"
    r"(?![A-Za-z0-9_./-])"
)


def _shown(value: str | None) -> str:
    return "not resolved" if value is None else json.dumps(value, ensure_ascii=True)


def install_clm_note(context: Any, note: dict[str, str]) -> int:
    """Replace only the pinned note this context itself identifies as ours."""
    prior = getattr(context, "_managed_facts_pin_index", None)
    if (type(prior) is int and 0 <= prior < len(context.pinned)
            and context.pinned[prior].get("role") == "user"
            and str(context.pinned[prior].get("content", "")).startswith("[core facts]\n")):
        index = prior
        context.pinned[index] = note
    else:
        index = len(context.pinned)
        context.pinned.append(note)
    context._managed_facts_pin_index = index
    return index


class Facts:
    """Observed fields and their age; unobserved world state remains unknown."""

    def __init__(self, env: Environment, workdir: str, remaining: Callable[[], float],
                 trace: Callable[..., None], *, terminal_state: Callable[[str], dict | None] | None = None,
                 python_state: Callable[[], dict] | None = None,
                 hosts: tuple[tuple[str, int], ...] | None = None):
        self.env, self.workdir, self.remaining, self.trace = env, workdir, remaining, trace
        self.terminal_state = terminal_state
        self.python_state = python_state
        self.hosts = facts_probe.HOSTS if hosts is None else hosts
        self.snapshot: dict[str, Any] | None = None
        self.shared_known = False
        self.last_shared_step: int | None = None
        self.last_full_step: int | None = None
        self.last_attempted_step: int | None = None
        self.memory_step: int | None = None
        self.terminal_paths: dict[str, dict[str, bool] | None] = {}
        self.terminal_steps: dict[str, int] = {}
        self.terminal_sessions: dict[str, dict[str, Any]] = {}
        self.python_session: dict[str, Any] | None = None
        self.probes = 0
        self.probe_seconds = 0.0
        self.last_finish_change: str | None = None
        self.bindings: dict[str, dict[str, Any]] = {}
        self.omitted_bindings = 0
        self.recent_differences: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.omitted_events = 0
        self.context_changed = False
        self.internal_failures = 0
        self.initial_workspace = InitialWorkspace()

    async def _observe(self, step: int, *, full: bool, watched: tuple[str, ...] = ()) -> dict[str, Any]:
        started = time.monotonic()
        result = await facts_probe.probe(
            self.env, self.workdir, full=full, remaining_s=self.remaining(), hosts=self.hosts, watched=watched,
        )
        elapsed = time.monotonic() - started
        self.last_attempted_step = step
        self.probes += 1
        self.probe_seconds += elapsed
        self.trace("core_facts_probe", step=step, full=full, ok=result["ok"],
                   duration_s=round(elapsed, 3))
        return result

    def _fault(self, stage: str, step: int, error: Exception) -> str:
        self.internal_failures += 1
        self.shared_known = False
        self.last_attempted_step = step
        self.context_changed = True
        for binding in self.bindings.values():
            binding.update(status="unknown", sha256=None, last_attempted_step=step)
        try:
            self.trace("core_facts_error", stage=stage, step=step, error_type=type(error).__name__)
        except Exception:
            pass
        return f"[core facts]\nObservation at step {step}: unmeasured."

    async def start(self) -> str:
        try:
            return await self._start()
        except Exception as exc:
            return self._fault("start", 0, exc)

    async def _start(self) -> str:
        result = await self._observe(0, full=True)
        if not result["ok"]:
            self.shared_known = False
            return "[core facts]\nShared probe at step 0: unmeasured."
        self.snapshot = result["facts"]
        self.initial_workspace.capture(self.snapshot.get("workspace"))
        self.shared_known = True
        self.last_shared_step = self.last_full_step = self.memory_step = 0
        if self.python_state is not None:
            python = self.python_state()
            if isinstance(python, dict) and python.get("preflight_python_version"):
                self.python_session = dict(python)
                self.python_session["last_observed_step"] = 0
        return self._context_summary()

    def _initial(self, facts: dict[str, Any], step: int, full_step: int | None = None) -> str:
        full_step = step if full_step is None else full_step
        commands = facts["commands"]
        directories: dict[str, list[str]] = {}
        individual = []
        for name, path in commands.items():
            if path is not None:
                directory, basename = posixpath.split(path)
                if path.startswith("/") and basename == name and directory:
                    directories.setdefault(directory, []).append(name)
                else:
                    individual.append(f"{name}={_shown(path)}")
        available = [f"{_shown(directory)}: {', '.join(names)}" for directory, names in directories.items()]
        available.extend(individual)
        missing = [name for name, path in commands.items() if path is None]
        versions = [f"{name}={version}" for name, version in (facts["versions"] or {}).items() if version]
        unmeasured = [name for name, version in (facts["versions"] or {}).items() if not version]
        if unmeasured:
            versions.append("unmeasured: " + ", ".join(unmeasured))
        managers = [name for name in facts_probe.MANAGERS if commands.get(name) is not None]
        network = [f"{host}={state}" for host, state in (facts["network"] or {}).items()]
        memory = facts["host_available_memory_kib"]
        workspace = facts["workspace"]
        lines = [
            "[core facts]",
            f"Shared probe PATH at step {step} (directory: command names): " +
            ("; ".join(available) or "no listed commands resolved") + ".",
            "Names not resolved on that PATH: " + (", ".join(missing) or "none") + ".",
            "Package-manager names resolved: " + (", ".join(managers) or "none") + ".",
            f"Version output at step {full_step}: " + (", ".join(versions) or "unmeasured") + ".",
            f"Permitted non-hidden entries in task workspace root at step {step}: " +
            (", ".join(facts["files"]) or "none observed") +
            ("; incomplete." if not facts["files_complete"] else "."),
            f"TCP probes at step {full_step}: " + (", ".join(network) or "unmeasured") + ".",
            f"Kernel-reported host available memory at step {self.memory_step if self.memory_step is not None else step}: " +
            (f"{memory} KiB." if memory is not None else "unmeasured."),
            (f"Workspace metadata scan at step {step}: " +
             (f"{len(workspace['files'])} eligible files; " +
              ("complete within the stated bounds." if workspace["complete"] else "incomplete.")
              if workspace is not None else "unmeasured.")),
            "Scope: shared probe shell; terminal PATHs, package contents, program behavior, "
            "container memory limits, excluded entries and later changes are unobserved.",
        ]
        return "\n".join(lines)

    def _terminal_delta(self, step: int, name: str) -> list[str]:
        if self.terminal_state is None or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            return []
        observed = self.terminal_state(name)
        previous_session = self.terminal_sessions.get(name, {})
        if isinstance(observed, dict):
            self.terminal_sessions[name] = {
                key: observed.get(key) for key in ("generation", "foreground", "last_observed_cwd",
                                                   "cwd_receipt_seq", "last_command_seq", "background_processes")
            }
            self.terminal_sessions[name]["last_observed_step"] = step
        else:
            self.terminal_sessions[name] = {"foreground": "unmeasured", "last_attempted_step": step,
                                            "background_processes": "unknown"}
        self.context_changed |= any(
            previous_session.get(key) != self.terminal_sessions[name].get(key)
            for key in ("generation", "foreground", "last_observed_cwd")
        )
        lookup = observed.get("command_resolution") if isinstance(observed, dict) else None
        self.terminal_steps[name] = step
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
        if prior is None and self.snapshot and self.shared_known:
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
        if not previous:
            resolved = [key for key, value in current.items() if value]
            missing = [key for key, value in current.items() if not value]
            return [f"Terminal {json.dumps(name)} PATH at step {step}: "
                    f"resolved {', '.join(resolved) or 'none'}; not resolved {', '.join(missing) or 'none'}."]
        return ([f"Terminal {json.dumps(name)} PATH observed at step {step}: " + ", ".join(changes) + "."]
                if changes else [])

    async def after_action(self, step: int, tool: str, args: dict, result: str, *,
                           call_id: str | None = None) -> str:
        try:
            return await self._after_action(step, tool, args, result, call_id=call_id)
        except Exception as exc:
            note = self._fault("after_action", step, exc)
            if tool == "finish":
                self.last_finish_change = note
                return ""
            return note

    async def _after_action(self, step: int, tool: str, args: dict, result: str, *,
                            call_id: str | None = None) -> str:
        self.context_changed = False
        updates = self._terminal_delta(step, str(args.get("name") or "main")) if tool == "terminal" else []
        if tool == "python" and self.python_state is not None:
            self.python_session = dict(self.python_state())
            self.python_session["last_observed_step"] = step
            self.context_changed = True
        command = str(args.get("input") or args.get("code") or "")
        mentioned = self._mentioned(tool, command)
        watched = tuple(dict.fromkeys((*self.bindings, *mentioned)))[:facts_probe.MAX_WATCHED]
        self.omitted_bindings += len(set(mentioned) - set(watched))
        full = tool != "finish" and (self.snapshot is None or step % 10 == 0 or bool(_FULL_REFRESH.search(command)))
        observation = await self._observe(step, full=full, watched=watched)
        if not observation["ok"]:
            if self.shared_known:
                updates.append(f"Shared probe at step {step}: unmeasured; last observed at step {self.last_shared_step}.")
            self.shared_known = False
            updates.extend(self._update_bindings(None, [], step))
        else:
            current = observation["facts"]
            initial_updates = self.initial_workspace.observe(current.get("workspace"), step)
            updates.extend(initial_updates)
            self.context_changed |= bool(initial_updates)
            old = self.snapshot
            if old is None:
                self.memory_step = step
                updates.extend(self._initial(current, step).splitlines()[1:])
            elif not self.shared_known:
                updates.append(f"Shared probe at step {step}: observed again.")
            if old is not None:
                self.context_changed |= (old["files"], old["files_complete"]) != (
                    current["files"], current["files_complete"]
                )
                completed = ((tool == "write_file" and result.startswith("wrote ")) or
                             (tool == "edit_file" and result.startswith("edited ")))
                authored = self._authored_top_level(tool, args) if completed else None
                updates.extend(self._changes(old, current, step, full, authored))
                updates.extend(self._workspace_changes(old.get("workspace"), current.get("workspace"), step, authored))
                if not full:
                    for key in ("versions", "network"):
                        current[key] = old[key]
                    current["host_available_memory_kib"] = old["host_available_memory_kib"]
                else:
                    self.memory_step = step
                    self.context_changed = True
            self.snapshot = current
            self.shared_known = True
            self.last_shared_step = step
            if full:
                self.last_full_step = step
            updates.extend(self._update_bindings(current.get("workspace"), mentioned, step))
        self._record_event(step, tool, call_id, result)
        if tool == "finish":
            self.last_finish_change = "\n".join(updates) or None
            return ""
        return "[core facts]\n" + "\n".join(updates) if updates else ""

    def _record_event(self, step: int, tool: str, call_id: str | None, result: str) -> None:
        workspace = self.snapshot.get("workspace") if self.snapshot and self.shared_known else None
        metadata = (json.dumps({"root": workspace["root"], "files": workspace["files"]},
                               sort_keys=True, separators=(",", ":")).encode() if workspace is not None else None)
        output_digest = (hashlib.sha256(result.encode("utf-8", errors="surrogatepass")).hexdigest()
                         if len(result) <= 256_000 else None)
        row = {
            "step": step, "tool": tool,
            "call_id": call_id if isinstance(call_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", call_id) else None,
            "tool_output_sha256": output_digest,
            "tool_output_scope": "raw tool result before facts and clock; UTF-8 with surrogatepass",
            "workspace_metadata_sha256": hashlib.sha256(metadata).hexdigest() if metadata is not None else None,
            "workspace_status": "observed" if workspace is not None else "unknown",
            "workspace_complete": workspace["complete"] if workspace is not None else None,
            "state_scope": "bounded scan after action; not necessarily the state read by the tool",
        }
        if len(self.events) >= 128:
            self.events.pop(0)
            self.omitted_events += 1
        self.events.append(row)

    @staticmethod
    def _mentioned(tool: str, command: str) -> list[str]:
        if tool not in ("terminal", "python"):
            return []
        return list(dict.fromkeys(path for path in _MENTIONED_PATH.findall(command)
                                  if facts_probe.safe_relative(path)))[:facts_probe.MAX_WATCHED]

    @staticmethod
    def _workspace_changes(old: dict | None, current: dict | None, step: int,
                           authored: str | None) -> list[str]:
        if current is None:
            return [f"Workspace metadata scan at step {step}: unmeasured."] if old is not None else []
        if old is None:
            return [f"Workspace metadata scan at step {step}: observed again; "
                    "changes while unmeasured are unknown."]
        if old["root"] != current["root"]:
            return [f"Workspace root identity changed at step {step}; earlier observations describe another root."]
        before, after = old["files"], current["files"]
        modified = sorted(name for name in set(before) & set(after)
                          if before[name] != after[name] and name != authored)
        added = sorted(set(after) - set(before) - {authored})
        removed = sorted(set(before) - set(after))
        complete = old["complete"] and current["complete"]
        details = []
        if modified:
            details.append("metadata changed for " + ", ".join(json.dumps(x) for x in modified[:10]))
        if added:
            noun = "added" if complete else "new to the observed sample"
            details.append(noun + " " + ", ".join(json.dumps(x) for x in added[:10]))
        if removed:
            noun = "removed" if complete else "not in the observed sample"
            details.append(noun + " " + ", ".join(json.dumps(x) for x in removed[:10]))
        if old["complete"] != current["complete"]:
            details.append("scan coverage is " + ("complete within bounds" if current["complete"] else "incomplete"))
        return [f"Workspace metadata at step {step}: " + "; ".join(details) + "."] if details else []

    def _update_bindings(self, workspace: dict | None, mentioned: list[str], step: int) -> list[str]:
        observed = workspace["fingerprints"] if workspace is not None else {}
        updates = []
        for path, binding in self.bindings.items():
            row = observed.get(path, {"status": "unknown"})
            status = row["status"]
            if workspace is not None and binding.get("root") != workspace["root"]:
                binding.update(status="unknown", sha256=None, last_attempted_step=step)
                continue
            if status == "observed" and binding["status"] == "observed" and row["sha256"] != binding["sha256"]:
                updates.append(f"Command text at step {binding['mention_step']} mentioned {json.dumps(path)}; "
                               f"its post-action fingerprint differs at step {step}.")
                self.recent_differences = (self.recent_differences +
                                           [{"path": path, "mention_step": binding["mention_step"], "step": step}])[-8:]
            elif status != "observed" and binding["status"] == "observed":
                updates.append(f"Fingerprint for {json.dumps(path)} at step {step}: {status}.")
            binding.update(status=status, sha256=row.get("sha256"), last_attempted_step=step)
            if status == "observed":
                binding["last_observed_step"] = step
        for path in mentioned:
            row = observed.get(path, {"status": "unknown"})
            if row["status"] == "observed":
                self.bindings[path] = {"status": "observed", "sha256": row["sha256"],
                                       "mention_step": step, "last_observed_step": step,
                                       "root": list(workspace["root"])}
        return updates

    def context_summary(self) -> str:
        try:
            return self._context_summary()
        except Exception as exc:
            return self._fault("context_summary", self.last_attempted_step or 0, exc)

    def _context_summary(self) -> str:
        if self.snapshot is None:
            return f"[core facts]\nShared probe at step {self.last_attempted_step}: unmeasured."
        note = self._initial(self.snapshot, self.last_shared_step or 0, self.last_full_step)
        if not self.shared_known:
            note += f"\nShared probe at step {self.last_attempted_step}: unmeasured; prior readings are historical."
        shared = self.snapshot["commands"]
        for name, values in list(self.terminal_paths.items())[-8:]:
            step = self.terminal_steps.get(name, "unknown")
            session = self.terminal_sessions.get(name, {})
            note += (f"\nTerminal {json.dumps(name)} foreground at step {step}: "
                     f"{session.get('foreground', 'unmeasured')}.")
            cwd = session.get("last_observed_cwd")
            if isinstance(cwd, str) and len(cwd) <= 256:
                note += f"\nTerminal {json.dumps(name)} cwd at step {step}: {json.dumps(cwd)}."
            if values is None:
                note += f"\nTerminal {json.dumps(name)} PATH at step {step}: unmeasured."
                continue
            different = [f"{key}={'resolved' if value else 'not resolved'}" for key, value in values.items()
                         if value != (shared.get(key) is not None)]
            note += (f"\nTerminal {json.dumps(name)} PATH at step {step}: " +
                     (", ".join(different[:10]) if different else "no tracked name differences") +
                     f" compared with the shared probe at step {self.last_shared_step}.")
        for item in self.recent_differences:
            note += (f"\nCommand text at step {item['mention_step']} mentioned {json.dumps(item['path'])}; "
                     f"its post-action fingerprint differed at step {item['step']}.")
        for notice in self.initial_workspace.context():
            note += "\n" + notice
        for path, binding in list(self.bindings.items())[-8:]:
            note += (f"\nLatest command-text mention of {json.dumps(path)}: step {binding['mention_step']}; "
                     f"fingerprint status {binding['status']} at attempted step "
                     f"{binding.get('last_attempted_step', binding['last_observed_step'])}.")
        if self.python_session:
            note += (f"\nPython session at step {self.python_session['last_observed_step']}: "
                     f"{self.python_session.get('foreground', 'unmeasured')}; variables not inspected.")
            version = self.python_session.get("preflight_python_version")
            if version:
                note += f"\nPython3 preflight before REPL launch reported version {version}."
        return note

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
                    updates.append(f"Permitted non-hidden task workspace root entries at step {step}: {detail}.")
            else:
                updates.append(f"Permitted non-hidden task workspace root entry sample changed at step {step}; "
                               "coverage incomplete or changed.")
        if full:
            if old["host_available_memory_kib"] != current["host_available_memory_kib"]:
                memory = current["host_available_memory_kib"]
                updates.append(f"Kernel-reported host available memory at step {step}: " +
                               (f"{memory} KiB." if memory is not None else "unmeasured."))
            for name, value in current["versions"].items():
                if (old["versions"] or {}).get(name) != value:
                    updates.append(f"Version output at step {step}: {name}={value or 'unmeasured'}.")
            for host, value in current["network"].items():
                if (old["network"] or {}).get(host) != value:
                    updates.append(f"TCP probe at step {step}: {host}={value}.")
        return updates

    def record(self) -> dict[str, Any]:
        workspace = self.snapshot.get("workspace") if self.snapshot and self.shared_known else None
        initial_workspace, initial_changes = self.initial_workspace.record()
        return {"shared_known": self.shared_known, "last_shared_step": self.last_shared_step,
                "last_full_step": self.last_full_step, "snapshot": deepcopy(self.snapshot),
                "terminal_paths": deepcopy(self.terminal_paths), "probe_count": self.probes,
                "terminal_sessions": deepcopy(self.terminal_sessions),
                "python_session": deepcopy(self.python_session),
                "probe_seconds": self.probe_seconds, "finish_observations_not_shown": self.last_finish_change,
                "workspace": ({"status": "observed", "complete": workspace["complete"]}
                              if workspace is not None else {"status": "unknown",
                                                              "last_observed_step": self.last_shared_step}),
                "initial_workspace": initial_workspace, "initial_workspace_changes": initial_changes,
                "bindings": deepcopy(self.bindings), "omitted_bindings": self.omitted_bindings,
                "recent_differences": deepcopy(self.recent_differences),
                "events": deepcopy(self.events), "omitted_events": self.omitted_events,
                "internal_failures": self.internal_failures,
                "scope": "bounded observations; package contents, hidden entries and external state unobserved"}

    def safe_record(self) -> dict[str, Any]:
        try:
            return self.record()
        except Exception as exc:
            self._fault("record", self.last_attempted_step or 0, exc)
            return {"status": "unknown", "internal_failures": self.internal_failures}
