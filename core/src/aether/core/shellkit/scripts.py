"""The kit's shell commands, written into the task container at /tmp/.aether/bin (AETHER_CORE_SHELL_KIT).

POSIX sh and awk only, so they run on bare images; apply_patch and pyk need the kit's python (AETHER_KIT_PY, the
task's python3 or the harness's relocatable CPython) and say so when there is none. Commands that need Core
(view_image, ctx drop/stub, job start) append one tab-separated line to the queue; Core reads the queue after the
tool call (shellkit.Kit.after), so a command chain still runs in order and Core acts once it ends.
"""

ROOT = "/tmp/.aether"  # the scripts below say @R@; files() and scan() put the kit root in
KIT, BIN, JOBS = "@R@/kit", "@R@/bin", "@R@/jobs"
QUEUE, CTX_SAVE = f"{KIT}/queue", "@R@/ctx"

NEEDS_PY = """#!/bin/sh
if [ -z "$AETHER_KIT_PY" ]; then echo "{name}: needs python3, which this container does not have" >&2; exit 127; fi
exec "$AETHER_KIT_PY" {kit}/{script} "$@"
"""

VIEW_IMAGE = f"""#!/bin/sh
# view_image PATH...: the images are shown to you after this command ends.
[ $# -gt 0 ] || {{ echo "usage: view_image PATH..." >&2; exit 2; }}
n=0
for p in "$@"; do
  case "$p" in /*) ;; *) p="$PWD/$p" ;; esac
  if [ ! -f "$p" ]; then echo "view_image: no such file: $p" >&2; continue; fi
  printf 'view\\t%s\\n' "$p" >> {QUEUE}; n=$((n+1))
done
echo "view_image: $n image(s) will be shown after this command"
[ $n -gt 0 ]
"""

JOB = f"""#!/bin/sh
# job start NAME 'CMD' | wait NAME [SECONDS] | status | log NAME [LINES] | kill NAME
J={JOBS}
killtree() {{ for c in $(awk -v p="$1" '$4==p{{print $1}}' /proc/[0-9]*/stat 2>/dev/null); do killtree "$c"; done; kill "$1" 2>/dev/null; }}
show() {{ d=$J/$1
  if [ -f $d/exit ]; then st="exit $(cat $d/exit)"; else st="running"; fi
  echo "job $1: $st, $(( $(date +%s) - $(cat $d/start) ))s since start: $(cat $d/cmd)"; }}
cmd=$1; [ $# -gt 0 ] && shift
case "$cmd" in
start)
  [ $# -eq 2 ] || {{ echo "usage: job start NAME 'COMMAND'" >&2; exit 2; }}
  d=$J/$1
  if [ -f $d/pid ] && [ ! -f $d/exit ]; then echo "job $1 is already running" >&2; exit 1; fi
  rm -rf $d; mkdir -p $d; printf '%s\\n' "$2" > $d/cmd; date +%s > $d/start
  sh_=$(command -v bash || echo sh)
  ( "$sh_" -c "$2" > $d/log 2>&1 < /dev/null; echo $? > $d/exit.tmp; mv $d/exit.tmp $d/exit ) &
  echo $! > $d/pid
  printf 'jobstart\\t%s\\n' "$1" >> {QUEUE}
  echo "job $1 started; you will be told when it ends. Output: job log $1" ;;
wait)
  d=$J/$1; [ -d $d ] || {{ echo "no job $1" >&2; exit 1; }}
  end=$(( $(date +%s) + ${{2:-30}} ))
  while [ ! -f $d/exit ] && [ $(date +%s) -lt $end ]; do sleep 0.5; done
  [ -f $d/exit ] && : > $d/told
  show "$1"; tail -n 20 $d/log ;;
status)
  for d in $J/*/; do [ -d "$d" ] && show "$(basename "$d")"; done; true ;;
log)
  [ -d $J/$1 ] || {{ echo "no job $1" >&2; exit 1; }}; tail -n "${{2:-50}}" $J/$1/log ;;
kill)
  d=$J/$1; [ -f $d/pid ] || {{ echo "no job $1" >&2; exit 1; }}
  killtree "$(cat $d/pid)"; sleep 0.2
  [ -f $d/exit ] || echo killed > $d/exit; : > $d/told; show "$1" ;;
*) echo "usage: job start NAME 'COMMAND' | wait NAME [SECONDS] | status | log NAME [LINES] | kill NAME" >&2; exit 2 ;;
esac
"""

CTX = f"""#!/bin/sh
# ctx list | drop TURN... | stub TURN...  (TURN: N or N-M, numbers from ctx list)
[ -n "$AETHER_CTX" ] && [ -f "$AETHER_CTX" ] || {{ echo "ctx: no editable context in this run" >&2; exit 1; }}
cmd=$1; [ $# -gt 0 ] && shift
blocks() {{ awk '
  function out() {{ if (n != "") printf "%5d %-9s %7d  %s\\n", n, role, chars, first; total += chars }}
  /^\\[\\[CTX_TURN [0-9]+ role=[a-z_]+\\]\\]$/ {{ out(); n = $2; role = substr($3, 6, length($3) - 7); chars = 0; first = ""; next }}
  {{ chars += length($0) + 1; if (first == "" && $0 ~ /[^ ]/) first = substr($0, 1, 70) }}
  END {{ out(); printf "total %d chars (~%d tokens)\\n", total, total / 4 }}' "$AETHER_CTX"; }}
case "$cmd" in
list) echo " turn role        chars  first line"; blocks ;;
drop|stub)
  [ $# -gt 0 ] || {{ echo "usage: ctx $cmd TURN..." >&2; exit 2; }}
  for t in "$@"; do case "$t" in *[!0-9-]*|-*|*-) echo "ctx: bad turn $t (N or N-M)" >&2; exit 2 ;; esac; done
  if [ "$cmd" = stub ]; then mkdir -p {CTX_SAVE}
    for t in "$@"; do a=${{t%-*}}; b=${{t#*-}}; i=$a
      while [ "$i" -le "$b" ]; do
        awk -v n="$i" '/^\\[\\[CTX_TURN [0-9]+ role=/ {{ on = ($2 == n); next }} on' "$AETHER_CTX" > {CTX_SAVE}/turn-$i.txt
        i=$((i+1)); done; done; fi
  printf 'ctx\\t%s\\t%s\\n' "$cmd" "$*" >> {QUEUE}
  echo "ctx: $cmd $* will apply to your context when this command ends" ;;
*) echo "usage: ctx list | drop TURN... | stub TURN..." >&2; exit 2 ;;
esac
"""

# One exec after a tool call: hand over the queue and report each job that ended and was not yet reported.
_SCAN = (
    f"Q={QUEUE}; if [ -s $Q ]; then mv $Q $Q.r; cat $Q.r; rm -f $Q.r; fi; "
    f"for d in {JOBS}/*/; do if [ -f \"$d/exit\" ] && [ ! -f \"$d/told\" ]; then "
    "printf 'jobdone\\t%s\\t%s\\n' \"$(basename \"$d\")\" \"$(cat \"$d/exit\")\"; : > \"$d/told\"; fi; done; true"
)


def scan(root: str) -> str:
    return _SCAN.replace("@R@", root)


def files(root: str, py_sources: dict[str, str]) -> dict[str, tuple[str, bool]]:
    """{container path: (text, executable)} for the whole kit."""
    out = {f"{KIT}/{name}": (text, False) for name, text in py_sources.items()}
    out[f"{BIN}/view_image"] = (VIEW_IMAGE, True)
    out[f"{BIN}/job"] = (JOB, True)
    out[f"{BIN}/ctx"] = (CTX, True)
    out[f"{BIN}/apply_patch"] = (NEEDS_PY.format(name="apply_patch", kit=KIT, script="patch_cli.py"), True)
    out[f"{BIN}/pyk"] = (NEEDS_PY.format(name="pyk", kit=KIT, script="pyk.py"), True)
    return {path.replace("@R@", root): (text.replace("@R@", root), x) for path, (text, x) in out.items()}
