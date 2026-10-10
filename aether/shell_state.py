"""Persistent shell state for ``run_command`` on the opt-in edit surface.

Each ``run_command`` runs in a fresh shell, so models re-type ``cd /app && ...``
and ``set ...`` on nearly every call.  This wrapper makes the working directory
and exported environment variables persist across commands, without touching
the command's exit code, stdout, or stderr:

* before the command: source the saved export file, then ``cd`` to the saved
  directory (a missing directory is ignored, leaving the starting directory);
* after the command (an ``EXIT`` trap, so ``exit 3`` and failures are covered):
  record ``pwd`` and ``export -p`` (plus ``unset`` lines for variables that were
  exported at first use and are gone now) into a per-run state directory outside
  the workspace.

The whole preamble is one line placed before the user's text so the user's own
line numbers in shell error messages are unchanged.  Limits: a command that
installs its own ``EXIT`` trap, ``exec``s, or is killed by its timeout does not
save state; background processes and shell options (``set -e``) do not persist.
The command is run by bash.
"""
from __future__ import annotations

import shlex

STATE_ROOT = "/tmp/.aether_shell_state"


def persistent_shell_command(command: str, *, state_id: str) -> str:
    """Wrap ``command`` so cwd and exported variables persist between calls."""
    if not state_id or not all(c.isalnum() or c in "-_" for c in state_id):
        raise ValueError("shell state id must be alphanumeric, '-' or '_'")
    state = shlex.quote(f"{STATE_ROOT}/{state_id}")
    save = (
        "__aes() { local __rc=$?; { set +ex; } 2>/dev/null; "
        "pwd > \"$__ST/cwd.t\" 2>/dev/null && mv -f \"$__ST/cwd.t\" \"$__ST/cwd\" 2>/dev/null; "
        "{ export -p; while IFS= read -r __n; do "
        "[ \"${!__n+x}\" ] || printf 'unset %s\\n' \"$__n\"; done < \"$__ST/base\"; } "
        "> \"$__ST/env.t\" 2>/dev/null && mv -f \"$__ST/env.t\" \"$__ST/env.sh\" 2>/dev/null; "
        "return $__rc; }"
    )
    preamble = (
        f"__ST={state}; mkdir -p \"$__ST\" 2>/dev/null; "
        "[ -f \"$__ST/base\" ] || compgen -e > \"$__ST/base\" 2>/dev/null; "
        "[ -f \"$__ST/env.sh\" ] && . \"$__ST/env.sh\" 2>/dev/null; "
        "[ -f \"$__ST/cwd\" ] && { IFS= read -r __D < \"$__ST/cwd\" && cd -- \"$__D\" 2>/dev/null; }; "
        f"{save}; trap '{{ __aes; }} 2>/dev/null' EXIT; "
    )
    return preamble + command
