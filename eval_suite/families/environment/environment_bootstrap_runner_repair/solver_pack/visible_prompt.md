# Task: Repair runner and toolchain contract

You are in a Python repo with stale docs and competing runner scripts.

Goal:
- identify the canonical test runner command,
- apply the necessary repair,
- produce `candidate/toolchain_repair_report.json`, and
- list edited files in `candidate/patches_applied.txt`.

Required report fields:
- `runner_command`
- `package_manager`
- `preflight_success`
- `evidence`

Do not rely on stale docs alone; verify with actual command behavior.
