"""``apply_patch`` shell command, run inside the task container by the kit's python (AETHER_CORE_SHELL_KIT).

Reads a Codex-format patch from stdin (or a file argument) and applies it relative to the current directory with
the same parser as Core's apply_patch tool (patch_text.py, copied beside this file). Every file's new text is
computed before anything is written; a patch that does not apply writes nothing and exits 1.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from patch_text import PatchError, parse, updated  # noqa: E402


def main(argv: list[str]) -> int:
    text = open(argv[1]).read() if len(argv) > 1 and argv[1] != "-" else sys.stdin.read()
    try:
        plan = []  # (tag, path, data or None)
        for hunk in parse(text):
            path = os.path.abspath(hunk.path)
            if hunk.kind == "add":
                plan.append(("A", path, "\n".join(hunk.lines) + "\n"))
                continue
            if not os.path.isfile(path):
                raise PatchError(f"{hunk.path}: file does not exist")
            if hunk.kind == "delete":
                plan.append(("D", path, None))
                continue
            with open(path, encoding="utf-8", newline="") as f:
                source = f.read()
            data = updated(source, hunk) if hunk.chunks else source
            if hunk.move_to:
                plan += [("D", path, None), ("M", os.path.abspath(hunk.move_to), data)]
            else:
                plan.append(("M", path, data))
    except (PatchError, UnicodeDecodeError, OSError) as exc:
        print(f"apply_patch: {exc}\nnothing was written", file=sys.stderr)
        return 1
    for tag, path, data in plan:
        if data is None:
            os.remove(path)
        else:
            os.makedirs(os.path.dirname(path) or "/", exist_ok=True)
            mode = os.stat(path).st_mode if os.path.exists(path) else None
            tmp = f"{path}.aether-patch"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(data)
            if mode is not None:
                os.chmod(tmp, mode)
            os.replace(tmp, path)
    print("Success. Updated the following files:\n" + "\n".join(f"{t} {p}" for t, p, _ in plan))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
