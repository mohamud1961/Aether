#!/usr/bin/env python3
"""Single source of truth: build normalized_attempt_rows.jsonl for all 482
discovered attempts and print every aggregate cited in the analysis.

Read-only against the frozen bundle. All conclusions downstream must be
reproducible from the emitted JSONL.
"""
import json
import re
from pathlib import Path
from collections import Counter, defaultdict

BUNDLE = Path("tracking/collab/vm_pulls/tracking/collab/"
              "aether2_g5_failure_analysis_clean_20260613T121431Z")
OUT = Path("tracking/collab/aether2_g5_run_analysis_20260613")
REL_BUNDLE = str(BUNDLE)

# ---- load captured authoritative rows (24) ----
authoritative = json.loads((OUT / "scripts" / "authoritative_attempt1.json").read_text())
cap = {r["task_id"]: r for r in authoritative}

# ---- load progress.tsv (482) ----
prog = []  # list of (attempt, task, rc, elapsed, date)
for line in (BUNDLE / "progress.tsv").read_text().splitlines():
    if not line.strip():
        continue
    f = line.split("\t")
    prog.append((int(f[0]), f[1], int(f[2]), int(f[3]), f[4]))

# ---- which logs are import-crash vs real vs empty ----
# Determined earlier: 457 identical import-crash logs; 24 real; 1 empty.
def log_path(att, task):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", task)
    return f"{REL_BUNDLE}/logs/attempt_{att}_{safe}.log"


def classify(att, task, rc, elapsed):
    """Return (validity_status, primary_class, contributing, confidence,
    authoritative_pass, external_verifier_status, diagnosis)."""
    row = cap.get(task) if att == 1 else None
    # Attempt-2: everything is import-crash (verified: 241/241 logs identical)
    if att == 2:
        return ("INVALID_LAUNCH_CONTAMINATED", "environment/runtime",
                ["process/service/session persistence", "contamination"], "high",
                None, "not_run",
                "Post-reboot autorestart ran in an env without repo root on "
                "sys.path; `import runner` failed before any task work "
                "(ModuleNotFoundError: No module named 'runner'). Attempt-2 "
                "ran entirely in this poisoned env (12:06:24-12:07:13, all <=1s).")
    # Attempt-1
    if row is None:
        # not captured -> import-crash tail OR the timeout
        if rc == 143:
            return ("VALID_RUN_TIMEOUT", "timeout/step-budget", [], "high",
                    None, "not_run",
                    "Real run, SIGTERM at elapsed=%ds; no row.json written "
                    "(killed before grading). Outcome UNCLEAR." % elapsed)
        return ("INVALID_LAUNCH", "environment/runtime",
                ["process/service/session persistence"], "high",
                None, "not_run",
                "Import-crash launch (ModuleNotFoundError: No module named "
                "'runner') after the 12:05 reboot autorestart; no real run, "
                "no row.json. elapsed=%ds." % elapsed)
    # Captured row present
    rs = row["row_status"]
    vexit = row["verifier_exit_code"]
    reason = row["reason"]
    if rs == "pass":
        return ("VALID_SCORED", "n/a-pass", [], "high", True, "pass",
                "Authoritative pass: verifier_exit_code=0.")
    if reason == "runner_exception":
        det = row.get("details") or ""
        if "azure" in det.lower() or "ModelClientError" in det:
            return ("INVALID_RUN", "provider/model transport", ["schema/parsing"],
                    "high", False, "not_run",
                    "runner_exception: %s" % det)
        return ("INVALID_RUN", "environment/runtime", ["path/cwd"], "high",
                False, "not_run", "runner_exception: %s" % det)
    if reason == "docker_build_failed" or rs == "invalid_environment":
        return ("INVALID_RUN", "sandbox/container setup", [], "high",
                None, "not_run",
                "Docker image build failed in %ss; task never ran." % row["wall_time_sec"])
    if vexit == 127:
        return ("VALID_RUN_GRADER_EXEC_FAIL", "verification/grading",
                ["environment/runtime"], "medium", False, "fail_exec127",
                "Verifier/test harness exit 127 (command/env missing when "
                "running tests): %s" % (row.get("verifier_stderr_tail") or ""))
    if vexit == 1:
        fr = row["finalize_reason"]
        if fr == "task_done":
            return ("VALID_SCORED", "execution/reasoning",
                    ["verification/grading"], "medium", False, "fail",
                    "Agent declared task_done but external verifier failed "
                    "(false-positive completion). %s"
                    % (row.get("verifier_stdout_tail") or ""))
        return ("VALID_SCORED", "execution/reasoning", ["timeout/step-budget"],
                "medium", False, "fail",
                "Agent stopped (%s) without satisfying verifier (exit 1). %s"
                % (fr, row.get("verifier_stdout_tail") or ""))
    return ("UNCLEAR", "unclear", [], "low", None, "unknown",
            "Captured row with unexpected status rs=%s vexit=%s" % (rs, vexit))


rows_out = []
for (att, task, rc, elapsed, date) in prog:
    row = cap.get(task) if att == 1 else None
    lr_present = row is not None and row.get("finalize_reason") is not None
    (validity, primary, contrib, conf, auth_pass, ext_status, diag) = classify(att, task, rc, elapsed)
    rec = {
        "task_id": task,
        "attempt": att,
        "validity_status": validity,
        "authoritative_pass": auth_pass,
        "grader_reward": (row or {}).get("grader_reward") if row else None,  # always null in bundle
        "external_verifier_status": ext_status,
        "external_verifier_exit_code": (row or {}).get("verifier_exit_code") if row else None,
        "advisory_verifier_clean": (row or {}).get("verifier_clean") if row else None,
        "runtime_sec": elapsed,
        "wall_time_sec_row": (row or {}).get("wall_time_sec") if row else None,
        "steps": (row or {}).get("steps") if row else None,
        "model_calls": (row or {}).get("model_calls") if row else None,
        "tokens_fresh": (row or {}).get("tokens_fresh") if row else None,
        "tokens_cached": (row or {}).get("tokens_cached") if row else None,
        "cost": None,
        "contamination_status": ("contaminated_post_reboot_import_crash" if att == 2
                                 else ("invalidated_post_reboot_import_crash"
                                       if validity == "INVALID_LAUNCH" else "clean")),
        "primary_failure_class": primary,
        "contributing_classes": contrib,
        "confidence": conf,
        "progress_rc": rc,
        "difficulty": (row or {}).get("difficulty") if row else None,
        "category": (row or {}).get("category") if row else None,
        "finalize_reason": (row or {}).get("finalize_reason") if row else None,
        "has_authoritative_row": row is not None,
        "exact_evidence_paths": [
            f"{REL_BUNDLE}/progress.tsv (attempt {att}, task {task})",
            log_path(att, task),
        ] + ([f"{REL_BUNDLE}/rows/attempt1_rows_combined.jsonl (### FILE .../{task}/row.json)"]
             if row is not None else []),
        "diagnosis": diag,
    }
    rows_out.append(rec)

# write jsonl
outp = OUT / "normalized_attempt_rows.jsonl"
with outp.open("w") as f:
    for r in rows_out:
        f.write(json.dumps(r) + "\n")
print(f"wrote {outp} ({len(rows_out)} rows)")

# ===================== AGGREGATES =====================
def agg(att):
    rs = [r for r in rows_out if r["attempt"] == att]
    print(f"\n========== ATTEMPT {att} (n={len(rs)}) ==========")
    print("validity_status:", dict(Counter(r["validity_status"] for r in rs)))
    print("primary_failure_class:", dict(Counter(r["primary_failure_class"] for r in rs)))
    passes = [r for r in rs if r["authoritative_pass"] is True]
    print("authoritative passes:", len(passes), [r["task_id"] for r in passes])
    has_row = [r for r in rs if r["has_authoritative_row"]]
    print("has_authoritative_row:", len(has_row))

agg(1)
agg(2)

# pass-rate denominators (attempt 1)
a1 = [r for r in rows_out if r["attempt"] == 1]
n_pass = sum(1 for r in a1 if r["authoritative_pass"] is True)
n_valid_scored = sum(1 for r in a1 if r["validity_status"] == "VALID_SCORED")
n_grader_exec_fail = sum(1 for r in a1 if r["validity_status"] == "VALID_RUN_GRADER_EXEC_FAIL")
n_captured = sum(1 for r in a1 if r["has_authoritative_row"])
print("\n--- ATTEMPT-1 PASS-RATE DENOMINATORS ---")
print(f"all-attempt:         {n_pass}/241 = {n_pass/241:.3%}")
print(f"captured-rows:       {n_pass}/{n_captured} = {n_pass/n_captured:.2%}")
print(f"valid-scored:        {n_pass}/{n_valid_scored} = {n_pass/n_valid_scored:.2%}")
print(f"valid-scored+exec127:{n_pass}/{n_valid_scored+n_grader_exec_fail} = {n_pass/(n_valid_scored+n_grader_exec_fail):.2%}")

# ===================== CACHE / TOKEN (prediction 5) =====================
print("\n--- CACHE-HIT RATIO + FRESH TOKENS (captured rows w/ loop_result) ---")
tot_fresh = tot_cached = 0
per = []
for r in a1:
    if r["tokens_fresh"] is None:
        continue
    fr, ca = r["tokens_fresh"], r["tokens_cached"]
    tot_fresh += fr; tot_cached += ca
    ratio = ca / (ca + fr) if (ca + fr) else 0
    per.append((r["task_id"], r["difficulty"], fr, ca, ratio))
for t, d, fr, ca, ratio in per:
    print(f"  {t:32s} diff={d!s:7s} fresh={fr:7d} cached={ca:8d} cache_ratio={ratio:.1%}")
overall = tot_cached / (tot_cached + tot_fresh)
print(f"  OVERALL pooled cache ratio = {tot_cached}/{tot_cached+tot_fresh} = {overall:.1%}")
n_ge80 = sum(1 for *_, ratio in per if ratio >= 0.80)
print(f"  rows with cache ratio >=80%: {n_ge80}/{len(per)}")
hard = [(t, fr) for t, d, fr, ca, ratio in per if d == "hard"]
print(f"  HARD tasks fresh tokens (<=150k pred): {hard}")

# predicted-task locations
print("\n--- PREDICTION-NAMED TASK STATUS (attempt 1) ---")
for t in ["qemu-startup", "extract-moves-from-video", "install-windows-3.11",
          "video-processing"]:
    rr = next((r for r in a1 if r["task_id"] == t), None)
    if rr:
        print(f"  {t}: validity={rr['validity_status']} has_row={rr['has_authoritative_row']} rc={rr['progress_rc']} elapsed={rr['runtime_sec']}s")
    else:
        print(f"  {t}: NOT FOUND in attempt-1 population")
