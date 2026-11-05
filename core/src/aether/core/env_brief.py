"""What the task's environment provides, measured once before the first action (AETHER_CORE_ENV_BRIEF=on).

Why (28 Oct, 422 Luna runs): 72% of runs hit a "command not found" or "No module named" (file, curl, python3, xxd,
numpy, PIL, ps, git, ...) and ~9% of all steps were spent discovering the environment, half of them in the first
five. The task message named only the working directory and the time limit. The brief is measured, not assumed:
one bounded shell probe of the task container, reported as found, never interpreted. Lists are fixed and generic
(common interpreters and tools); installed Python packages are listed as the interpreter reports them.

Revised after y5 (28 Oct): the first brief listed ~30 tools as "not installed" and never said whether software could
be installed. On a document task one run concluded it had only od/ps/perl and hand-parsed PDFs in perl; control runs
installed PDF/OCR tools by step 12-20 (y5 financial: 1/3 vs 3/3). The brief now reports the package managers and
whether their servers are reachable, and lists missing tools as not found rather than as a limit.

Extended 5 Nov: the machine as the container sees it (cpus, cgroup CPU quota, memory and its cgroup limit, free disk
at the working directory and /tmp), what lies outside the working directory (non-standard top-level directories and
the first entries of non-empty /opt, /srv, /mnt, homes, /root, /tmp) and the processes already running (by name).
Measured facts only, like the rest; nothing says what they mean for the task.
"""

from __future__ import annotations

import shlex

from .env import Environment, run

ENV_BRIEF_ENV = "AETHER_CORE_ENV_BRIEF"
TOOLS = ("python3", "python", "pip3", "pip", "node", "npm", "gcc", "g++", "cc", "make", "cmake", "git", "curl",
         "wget", "file", "xxd", "od", "strings", "nm", "objdump", "readelf", "gdb", "sqlite3", "jq", "rg", "ps",
         "ss", "netstat", "perl", "ruby", "go", "rustc", "cargo", "java", "R", "tesseract", "convert", "pdftotext",
         "chromium", "chromium-browser", "google-chrome", "firefox", "chromedriver",
         "sshd", "nginx", "apache2", "systemctl", "service")  # services: state v2 sizing (a missing daemon decided runs)
MANAGERS = ("apt-get", "apk", "dnf", "yum", "pip3", "pip", "npm")
# One host per ecosystem, probed with a 3 s TCP connect; reachability is reported, never assumed.
INDEXES = (("deb.debian.org", 80), ("archive.ubuntu.com", 80), ("dl-cdn.alpinelinux.org", 80), ("pypi.org", 443))
MAX_PACKAGES, MAX_ENTRIES, MAX_CHARS = 80, 60, 3000

_SCRIPT = r"""
os=$( (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || uname -sr)
echo "os: $os $(uname -m 2>/dev/null)"
have=""; miss=""
for t in {tools}; do if command -v "$t" >/dev/null 2>&1; then have="$have $t"; else miss="$miss $t"; fi; done
echo "available:$have"; echo "not found on PATH:$miss"
mg=""; for t in {managers}; do command -v "$t" >/dev/null 2>&1 && mg="$mg $t"; done
net=unknown
if command -v bash >/dev/null 2>&1 && command -v timeout >/dev/null 2>&1; then net=unreachable
  for hp in {indexes}; do h=${{hp%:*}}; p=${{hp#*:}}
    if timeout 3 bash -c "echo > /dev/tcp/$h/$p" 2>/dev/null; then net="reachable ($h)"; break; fi; done; fi
echo "package managers:${{mg:- none}}; package servers: $net"
py=$(command -v python3 || command -v python)
if [ -n "$py" ]; then
  echo "python: $($py -V 2>&1)"
  pk=$($py -c "import importlib.metadata as m; print(' '.join(sorted({{(d.metadata['Name'] or '').lower() for d in m.distributions()}} - {{''}})))" 2>/dev/null)
  n=$(echo "$pk" | wc -w | tr -d " "); echo "python packages ($n): $(echo $pk | tr ' ' '\n' | head -{maxp} | tr '\n' ' ')$( [ "$n" -gt {maxp} ] && echo '...')"
fi
cpu=$(nproc 2>/dev/null); q=$(cat /sys/fs/cgroup/cpu.max 2>/dev/null)
case "$q" in [0-9]*) cpu="$cpu (cgroup quota $(echo "$q" | awk '{{printf "%.1f", $1/$2}}'))";; esac
mt=$(awk '/MemTotal/{{print int($2/1024)}}' /proc/meminfo 2>/dev/null); ma=$(awk '/MemAvailable/{{print int($2/1024)}}' /proc/meminfo 2>/dev/null)
ml=$(cat /sys/fs/cgroup/memory.max 2>/dev/null); case "$ml" in [0-9]*) ml=", cgroup limit $((ml/1048576)) MiB";; *) ml="";; esac
echo "machine: cpus ${{cpu:-unknown}}; memory ${{mt:-?}} MiB total, ${{ma:-?}} MiB available$ml; disk free: $(df -Pm {wd} 2>/dev/null | awk 'NR==2{{print $4" MiB at "$6}}'), $(df -Pm /tmp 2>/dev/null | awk 'NR==2{{print $4" MiB at "$6}}')"
od=""; for d in /*; do case "${{d#/}}" in bin|boot|dev|etc|home|lib|lib32|lib64|libx32|media|mnt|opt|proc|root|run|sbin|srv|sys|tmp|usr|var) ;; *) [ "$d" = {wd} ] || od="$od $d";; esac; done
sk='\.(bashrc|profile|bash_logout|cache|config|local|npm|wget-hsts|bash_history)'
for d in /opt /srv /mnt /home/* /root /tmp; do [ -d "$d" ] && [ "$d" != {wd} ] || continue
  e=$(ls -A "$d" 2>/dev/null | grep -vxE "$sk" | head -8 | tr '\n' ' ' | sed 's/ $//'); [ -n "$e" ] && od="$od $d($e)"; done
echo "outside {wd} (non-standard or non-empty):${{od:- nothing}}"
pr=$(for p in /proc/[0-9]*; do [ "${{p#/proc/}}" = "$$" ] || cat "$p/comm" 2>/dev/null; done | grep -vxE 'bash|sh|dash|timeout|sort|cat|uniq|head|tr|find|awk|sed|ls|grep|wc|xargs' | sort | uniq | head -20 | tr '\n' ' ')
echo "running processes: ${{pr:-none besides this probe}}"
echo "files under {wd} (depth 2):"
cd {wd} 2>/dev/null && find . -mindepth 1 -maxdepth 2 -not -path '*/.git/*' 2>/dev/null | sort | head -{maxe} | while read -r p; do
  if [ -d "$p" ]; then echo "  $p/"; else echo "  $p ($(wc -c < "$p" 2>/dev/null | tr -d ' ') B)"; fi; done
[ "$(find . -mindepth 1 -maxdepth 2 -not -path '*/.git/*' 2>/dev/null | wc -l)" -gt {maxe} ] && echo "  ..."
"""


async def take(env: Environment, workdir: str) -> tuple[str, dict]:
    """One probe of the task container; returns the brief for the task message ('' on failure) and a trace row."""
    script = _SCRIPT.format(tools=" ".join(TOOLS), managers=" ".join(MANAGERS), maxp=MAX_PACKAGES, maxe=MAX_ENTRIES,
                            indexes=" ".join(f"{h}:{p}" for h, p in INDEXES), wd=shlex.quote(workdir))
    try:
        result = await run(env, script, timeout_s=30)
    except Exception as exc:  # an instrument: no brief, no claim
        return "", {"ok": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
    text = result.stdout.strip()
    if not text.startswith("os:"):
        return "", {"ok": False, "reason": (result.stderr or text)[:300], "exit": result.code}
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n  ..."
    return f"(Environment, measured by the harness before your first action:\n{text})", {"ok": True, "chars": len(text)}
