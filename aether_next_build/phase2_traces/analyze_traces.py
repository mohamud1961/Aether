#!/usr/bin/env python3.11
"""Turn Aether-Next run traces into a per-task, per-step audit + cross-model metrics."""
from __future__ import annotations
import json, sys, re, glob, os
from collections import Counter

ACTION_KINDS = {"run_command","read_file","write_file","inspect_artifact",
                "artifact_inspection","launch_process","probe_service",
                "register_candidate","run_experiment","bootstrap_acquire"}

def norm_cmd(obs):
    """A normalized signature for repeat detection."""
    s = obs.get("summary","")
    m = re.match(r"command exit=-?\d+: (.*)", s, re.S)
    body = m.group(1) if m else s
    return re.sub(r"\s+"," ", body).strip()[:400]

def load(path):
    d = json.load(open(path))
    return d, d["trace"]

def step_action_kinds(step):
    return [a.get("kind") for a in step["turn"].get("actions",[])]

def analyze_one(path):
    d, tr = load(path)
    steps = tr["steps"]; gates = tr["gate_decisions"]
    # per-step rows
    rows=[]; cmd_seen=Counter(); repeats=0; failures=0; state_changes=0
    distinct_cmds=set(); n_act=n_submit=n_recfg=n_invalid=0
    for s in steps:
        tk = s["turn"]["kind"]
        if tk=="act": n_act+=1
        elif tk=="submit_outcome": n_submit+=1
        elif tk=="request_reconfigure": n_recfg+=1
        obs=s.get("observations",[])
        # turn-level invalid?
        if any(o["kind"] in ("turn_validation","action_validation") for o in obs):
            n_invalid+=1
        step_repeat=False
        for o in obs:
            if o["kind"]=="run_command":
                sig=norm_cmd(o); distinct_cmds.add(sig)
                cmd_seen[sig]+=1
                if cmd_seen[sig]>1: step_repeat=True
            if o.get("success") is False: failures+=1
            if o.get("kind") in ("write_file",) or (o.get("kind")=="run_command" and o.get("success")):
                pass
        if step_repeat: repeats+=1
        rows.append((s["step"], tk, s["turn"].get("summary","")[:80], obs))
    total_cmd=sum(cmd_seen.values())
    repeat_cmds=sum(c for c in cmd_seen.values() if c>1) - len([c for c in cmd_seen.values() if c>1])
    return {
        "task": d["task"], "reward": d["reward"], "status": d["status"],
        "n_steps": len(steps), "n_act": n_act, "n_submit": n_submit,
        "n_recfg": n_recfg, "n_invalid_turns": n_invalid,
        "fallback": tr["architect_fallback_codes"],
        "selected_caps": tr["architect_config"].get("selected_capabilities"),
        "proc_mode": tr["architect_config"].get("process_policy",{}).get("mode"),
        "workflow": tr["architect_config"].get("workflow_policy",{}).get("mode"),
        "check_plan": tr["architect_config"].get("check_plan"),
        "proof_plan": tr["architect_config"].get("proof_plan"),
        "inspection_plan": tr["architect_config"].get("inspection_plan"),
        "n_distinct_cmds": len(distinct_cmds), "n_total_cmds": total_cmd,
        "n_repeat_cmds": max(0,total_cmd-len(distinct_cmds)),
        "n_cmd_failures": failures,
        "gates": [(g["step"], g["ready"], g.get("recommend_reconfigure"), g.get("blockers")) for g in gates],
        "rows": rows, "reconfigures": tr["reconfigures"],
    }

def fmt_obs(obs):
    parts=[]
    for o in obs:
        k=o["kind"]; ok="ok" if o.get("success") else "FAIL"
        if k=="run_command":
            cmd=norm_cmd(o)[:120]
            parts.append(f"`$ {cmd}` exit={o.get('exit_code')} {ok}")
        elif k in ("read_file","artifact_inspection","write_file"):
            parts.append(f"{k}:{o.get('path') or o.get('summary','')[:60]} {ok}")
        elif k=="check_result":
            parts.append(f"CHECK {o.get('summary','')} {ok}")
        else:
            parts.append(f"{k} {ok}")
    return " ; ".join(parts)

def emit_task_md(a):
    L=[]
    L.append(f"### {a['task']}  —  reward **{a['reward']}** / status `{a['status']}`")
    fb = ", ".join(a["fallback"]) if a["fallback"] else "none (architect config accepted)"
    L.append(f"- **Architect:** caps={a['selected_caps']} | mode={a['proc_mode']} | workflow={a['workflow']} | check_plan={a['check_plan']} | **fallback:** {fb}")
    L.append(f"- **Steps:** {a['n_steps']} (act {a['n_act']}, submit {a['n_submit']}, reconfig-req {a['n_recfg']}, invalid-turns {a['n_invalid_turns']})")
    L.append(f"- **Commands:** {a['n_total_cmds']} total, {a['n_distinct_cmds']} distinct, **{a['n_repeat_cmds']} repeated**, {a['n_cmd_failures']} failed")
    L.append(f"- **Verification (gate):** {a['gates'] or 'never reached submit gate'}")
    if a["reconfigures"]:
        L.append(f"- **Reconfigures:** {[(r['step'], r['reason']) for r in a['reconfigures']]}")
    L.append("")
    L.append("| step | turn | what it did | observations |")
    L.append("|---|---|---|---|")
    for (st,tk,summ,obs) in a["rows"]:
        L.append(f"| {st} | {tk} | {summ.replace('|','/')} | {fmt_obs(obs).replace('|','/')[:240]} |")
    L.append("")
    return "\n".join(L)

def main():
    d=sys.argv[1]
    files=sorted(glob.glob(os.path.join(d,"*.trace.json")))
    analyses=[analyze_one(f) for f in files]
    for a in analyses:
        print(emit_task_md(a))
    # summary metrics
    print("## Aggregate")
    print(f"- tasks: {len(analyses)} | rewarded: {sum(1 for a in analyses if a['reward']==1.0)}")
    print(f"- architect fallback rate: {sum(1 for a in analyses if a['fallback'])}/{len(analyses)}")
    print(f"- mean steps: {sum(a['n_steps'] for a in analyses)/max(1,len(analyses)):.1f}")
    print(f"- total repeated commands: {sum(a['n_repeat_cmds'] for a in analyses)}")
    print(f"- total failed commands: {sum(a['n_cmd_failures'] for a in analyses)}")

if __name__=="__main__":
    main()
