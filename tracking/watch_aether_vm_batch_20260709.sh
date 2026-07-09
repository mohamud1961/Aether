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

# Optimized SSH options to prevent hangs and timeout quickly
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=10 -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -i ~/.ssh/id_rsa)

while true; do
  # Perform a single SSH call to query all active task PIDs on the VM
  active_report=$(ssh "${SSH_OPTS[@]}" "azureuser@$IP" "
    for task in $TASKS; do
      pid=\$(cat \"$RUN_ROOT/\$task/pid\" 2>/dev/null || true)
      if [ -n \"\$pid\" ] && ps -p \"\$pid\" >/dev/null 2>&1; then
        echo -n \" \$task:\$pid\"
      fi
    done
  " 2>/dev/null || echo "ERROR_SSH")

  if [ "$active_report" = "ERROR_SSH" ]; then
    echo "poll=$(date -u +%Y-%m-%dT%H:%M:%SZ) error=SSH_FAILED" >> "$LOG"
    sleep 30
    continue
  fi

  # Trim leading spaces
  summary=$(echo "$active_report" | xargs)
  
  # Count active tasks
  if [ -z "$summary" ]; then
    alive=0
  else
    alive=$(echo "$summary" | wc -w | xargs)
  fi

  echo "poll=$(date -u +%Y-%m-%dT%H:%M:%SZ) alive=$alive $summary" >> "$LOG"

  if [ "$alive" -eq 0 ]; then
    echo "all_lanes_finished=$(date -u +%Y-%m-%dT%H:%M:%SZ); pulling results to host" >> "$LOG"
    
    # Pull results
    mkdir -p "/Users/mohamud/Downloads/harnesseng/aether_next_build/vm_goal_runs/${RUN_ID}"
    rsync -avz --exclude '__pycache__' -e "ssh -i ~/.ssh/id_rsa" "azureuser@$IP:/home/azureuser/harnesseng_vm/aether_next_build/vm_goal_runs/${RUN_ID}/" "/Users/mohamud/Downloads/harnesseng/aether_next_build/vm_goal_runs/${RUN_ID}/" >> "$LOG" 2>&1
    
    echo "pull_done=$(date -u +%Y-%m-%dT%H:%M:%SZ); deallocating $VM_NAME" >> "$LOG"
    az vm deallocate -g "$VM_RG" -n "$VM_NAME" >> "$LOG" 2>&1
    echo "deallocate_done=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
    exit 0
  fi

  sleep 60
done
