"""POSIX-shell twin of env's Python process observer, for task images without python3.

Same receipt format and semantics: ownership is the roots, their descendants by parent PID and members of process
groups a root leads, kept across observations by birth identity (``/proc`` start ticks, the precision the Python
observer uses on Linux) so a child whose parent exits is still owned and a recycled PID is never adopted. Without
``/proc`` it reports unverified: there is no portable shell enumeration it could trust.

Arguments: nonce, action (observe, list or stop), roots as JSON, roots space-separated, bindings ("pid=ticks ...",
empty for none). Found in the 2026-10-26 Modal baseline: 9/32 task images had no python3.
"""

SH_OBSERVER = r"""
nonce=$1; action=$2; roots_json=$3; roots=$4; bindings=$5
out() { printf 'AETHER_CLEANUP_V1 {"nonce":"%s","roots":%s,%s}\n' "$nonce" "$roots_json" "$1"; }
fail() { out "\"status\":\"unverified\",\"missing_roots\":[$2],\"observed\":[],\"still_running\":[],\"identity_changed\":[],\"signal_errors\":[{\"error\":\"RuntimeError\",\"detail\":\"$1\"}],\"identity_precision\":\"proc_start_ticks\",\"processes\":[]"; exit 1; }
csv() { printf '%s\n' $1 | awk 'NF{printf "%s%s", (n++?",":""), $1}'; }
[ -r /proc/self/stat ] || fail "no python3 and no /proc: process enumeration unavailable" ""
snap() {
  for d in /proc/[0-9]*; do
    s=$(cat "$d/stat" 2>/dev/null) || continue
    r=${s##*) }
    set -- $r
    printf '%s %s %s %s %s\n' "${d#/proc/}" "$2" "$3" "$1" "$(shift 19; printf '%s' "$1")"
  done
}
owned=""; reused=""
step() {
  S=$(snap)
  res=$(printf '%s\n' "$S" | awk -v roots="$roots" -v prev="$owned" '
    NF==5 {pp[$1]=$2; pg[$1]=$3; tk[$1]=$5}
    END {
      n=split(roots,a," "); for(i=1;i<=n;i++){ r[a[i]]=1; if(a[i] in pp) c[a[i]]=1 }
      m=split(prev,b," "); for(i=1;i<=m;i++){ split(b[i],kv,"=")
        if(!(kv[1] in tk)) continue
        if(tk[kv[1]]==kv[2]) c[kv[1]]=1; else print "U " kv[1] }
      ch=1; while(ch){ ch=0; for(p in pp) if(!(p in c) && ((pp[p] in c) || (pg[p] in r))){ c[p]=1; ch=1 } }
      for(p in c) print "O " p "=" tk[p] }')
  owned=$(printf '%s\n' $owned $(printf '%s\n' "$res" | awk '$1=="O"{print $2}') | awk 'NF && !s[$0]++' | tr '\n' ' ')
  reused=$(printf '%s\n' $reused $(printf '%s\n' "$res" | awk '$1=="U"{print $2}') | awk 'NF && !s[$0]++' | tr '\n' ' ')
}
row() { printf '%s\n' "$S" | awk -v p="$1" '$1==p'; }
alive() { r=$(row "${1%%=*}"); [ -n "$r" ] || return 1; set -- $r "$1"; [ "$4" != Z ] && [ "$4" != X ] && [ "$6" = "$1=$5" ]; }
S=$(snap); missing=""
for R in $roots; do [ -n "$(row "$R")" ] || missing="$missing $R"; [ "$R" = "$$" ] && fail "cleanup root is observer or ancestor" ""; done
[ -z "$missing" ] || fail "root absent before observation; descendant ownership unverified" "$(csv "$missing")"
for kv in $bindings; do
  r=$(row "${kv%%=*}"); set -- $r
  [ "$5" = "${kv#*=}" ] || fail "launch-time process identity unavailable or changed; no signals sent" ""
done
step
ids=""; for R in $roots; do r=$(row "$R"); set -- $r; ids="$ids${ids:+,}\"$R\":\"$5\""; done
if [ "$action" = observe ] || [ "$action" = list ]; then
  procs=""
  if [ "$action" = list ]; then
    for kv in $owned; do
      alive "$kv" || continue
      p=${kv%%=*}
      cmd=$(tr '\000' ' ' < "/proc/$p/cmdline" 2>/dev/null | tr -d '\001-\037' | sed 's/ *$//; s/\\/\\\\/g; s/"/\\"/g' | cut -c1-200)
      [ -n "$cmd" ] || { S=$(snap); alive "$kv" || continue; fail "live owned process command observation failed; retention unverified" ""; }
      procs="$procs${procs:+,}{\"pid\":$p,\"command\":\"$cmd\"}"
    done
  fi
  out "\"status\":\"observed\",\"processes\":[$procs],\"identities\":{$ids},\"identity_precision\":\"proc_start_ticks\""
  exit 0
fi
errors=""
for sig in TERM KILL; do
  step
  for kv in $owned; do alive "$kv" || continue; kill -s "$sig" "${kv%%=*}" 2>/dev/null; done
  sleep 0.15
done
i=0; survivors=""
while :; do
  step; survivors=""
  for kv in $owned; do alive "$kv" && survivors="$survivors ${kv%%=*}"; done
  [ -z "$survivors" ] && break; i=$((i+1)); [ "$i" -ge 30 ] && break; sleep 0.05
done
if [ -n "$survivors" ]; then status=still_running; elif [ -n "$reused" ]; then status=unverified; else status=confirmed_stopped; fi
observed=""; for kv in $owned; do observed="$observed ${kv%%=*}"; done
out "\"status\":\"$status\",\"missing_roots\":[],\"observed\":[$(csv "$observed")],\"still_running\":[$(csv "$survivors")],\"identity_changed\":[$(csv "$reused")],\"signal_errors\":[],\"identity_precision\":\"proc_start_ticks\",\"coverage\":\"shell observer (no python3): observed roots, descendants and anchored owned process groups; pre-observation detached/orphan processes are not proven owned\""
[ "$status" = confirmed_stopped ]
"""
