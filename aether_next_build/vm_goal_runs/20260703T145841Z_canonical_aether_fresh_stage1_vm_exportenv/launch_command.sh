#!/usr/bin/env bash
set -euo pipefail
cd /home/azureuser/harnesseng_vm/aether_next_build
set -a
source /home/azureuser/.aether2/model.env
set +a
export AETHER_VERIFIER_EVIDENCE_DIR=/home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/verifier_evidence
export PYTHONPATH=.
python3.11 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert \
  --tasks-dir /home/azureuser/harnesseng_vm/official_tasks \
  --architect-mode workbench \
  --effort low \
  --max-steps 10 \
  --run-timeout-s 1200 \
  --trace-dir /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/traces \
  --snapshot-dir /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/snapshots \
  --out /home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/20260703T145841Z_canonical_aether_fresh_stage1_vm_exportenv/results.json
