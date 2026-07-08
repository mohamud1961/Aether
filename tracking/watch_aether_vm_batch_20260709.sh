#!/usr/bin/env bash
# Usage: tracking/watch_aether_vm_batch_20260709.sh <run_id>
set -u

RUN_ID="${1:-20260709T000000Z_batch_15task_D16}"
RUN_ROOT="/home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/${RUN_ID}"
LOG="/Users/mohamud/Downloads/harnesseng/tracking/ledger/inbox/vm_D16_run_watchdog_${RUN_ID}.log"
VM_RG="Proteun"
VM_NAME="proteun-vm"
IP="74.249.212.125"
TASKS="log-summary-date-ranges gcode-to-text video-processing kv-store-grpc code-from-image openssl-selfsigned-cert fix-git git-multibranch regex-log write-compressor nginx-request-logging headless-terminal qemu-startup crack-7z-hash train-fasttext"

mkdir -p "$(dirname "$LOG")"
echo "watchdog_start=$(date -u +%Y-%m-%dT%H:%M:%SZ) run_root=$RUN_ROOT" >> "$LOG"

while true; do
  alive=0
  summary=""
  for task in $TASKS; do
    pid=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ~/.ssh/id_rsa "azureuser@$IP" "cat '$RUN_ROOT/$task/pid' 2>/dev/null" 2>/dev/null || true)
    if [ -n "$pid" ] && ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i ~/.ssh/id_rsa "azureuser@$IP" "ps -p '$pid' >/dev/null 2>&1" >/dev/null 2>&1; then
      alive=$((alive + 1))
      summary="$summary $task:$pid"
    fi
  done

  echo "poll=$(date -u +%Y-%m-%dT%H:%M:%SZ) alive=$alive$summary" >> "$LOG"

  if [ "$alive" -eq 0 ]; then
    echo "all_lanes_finished=$(date -u +%Y-%m-%dT%H:%M:%SZ); deallocating $VM_NAME" >> "$LOG"
    az vm deallocate -g "$VM_RG" -n "$VM_NAME" >> "$LOG" 2>&1
    echo "deallocate_done=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    exit 0
  fi

  sleep 60
done
