"""Skills the task environment provides, listed once at start (AETHER_CORE_SKILLS=on with a declared skills_dir).

Harbor passes a task's ``environment.skills_dir`` to the agent ("contents are copied to the agent's skills config
directory"); Claude Code and Codex list each skill's name and description up front and load the full instructions
only when one applies. Core previously ignored the declaration, so a task that ships skills ran without them.

One bounded, read-only probe: ``SKILL.md`` regular files (no links) at most two levels below the declared
directory, at most ``MAX_SKILLS``; from each, the ``name`` and ``description`` of its front matter. The note gives
name, description and path. Nothing is executed or interpreted; the model reads a SKILL.md with its normal tools.
A missing directory or a failed probe adds nothing and is recorded in the trace.
"""

from __future__ import annotations

import posixpath
import shlex

from .env import Environment, run

MAX_SKILLS, MAX_DESCRIPTION = 30, 300

_SCRIPT = r"""
d=$1
[ -d "$d" ] || { printf 'missing\n'; exit 0; }
find -P "$d" -mindepth 1 -maxdepth 3 -name SKILL.md -type f 2>/dev/null | sort | head -n {limit} | while IFS= read -r f; do
  printf 'F\t%s\n' "$f"
  head -n 40 "$f" | awk 'NR==1 && $0!="---" {exit} NR>1 && $0=="---" {exit} NR>1 {print "L\t" $0}'
done
printf 'done\n'
"""


def parse(stdout: str) -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    for line in stdout.splitlines():
        kind, _, text = line.partition("\t")
        if kind == "F":
            skills.append({"path": text, "name": posixpath.basename(posixpath.dirname(text)), "description": ""})
        elif kind == "L" and skills:
            key, sep, value = text.partition(":")
            value = value.strip().strip("'\"")
            if sep and key.strip() in ("name", "description") and value:
                skills[-1][key.strip()] = value[:MAX_DESCRIPTION]
    return skills


async def take(env: Environment, skills_dir: str) -> tuple[str, dict]:
    if not skills_dir.startswith("/"):
        return "", {"ok": False, "reason": "skills_dir is not absolute", "dir": skills_dir}
    script = _SCRIPT.replace("{limit}", str(MAX_SKILLS))
    try:
        result = await run(env, f"sh -c {shlex.quote(script)} core-skills {shlex.quote(skills_dir)}", timeout_s=20)
    except Exception as exc:  # an instrument: no note, no claim
        return "", {"ok": False, "reason": f"{type(exc).__name__}: {exc}"[:300], "dir": skills_dir}
    out = result.stdout.rstrip()
    if result.code != 0 or not out.endswith(("done", "missing")):
        return "", {"ok": False, "reason": (result.stderr or f"exit {result.code}")[:300], "dir": skills_dir}
    if out.endswith("missing"):
        return "", {"ok": True, "dir": skills_dir, "present": False, "skills": 0}
    skills = parse(out)
    row = {"ok": True, "dir": skills_dir, "present": True, "skills": len(skills)}
    if not skills:
        return "", row
    lines = "\n".join(f"- {s['name']}: {s['description'] or '(no description)'} ({s['path']})" for s in skills)
    return (f"(Skills provided by this environment in {skills_dir}. Each is a folder whose SKILL.md holds its "
            f"instructions; read one when it applies to your work:\n{lines})"), row
