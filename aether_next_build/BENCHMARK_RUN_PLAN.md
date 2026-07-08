# Benchmark Run Plan

This document defines the execution plan, run matrix, monitoring instructions, and stop/abort criteria for the upcoming diverse benchmark run batch of 15 TerminalBench-style tasks.

## 1. Run Matrix

| Task ID | Domain | Model (Solver/Verifier/Architect) | Concurrency | Timeout Policy | Retry Policy | Expected Result Location | Monitor |
|---|---|---|---|---|---|---|---|
| **log-summary-date-ranges** | File/Data | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **gcode-to-text** | File/Data | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **video-processing** | Perception | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **kv-store-grpc** | Service | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **code-from-image** | Perception | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **openssl-selfsigned-cert** | Security | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **fix-git** | Git | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **git-multibranch** | Git | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **regex-log** | Query | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **write-compressor** | Build | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **nginx-request-logging** | Service | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **headless-terminal** | Interactive | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **qemu-startup** | Interactive | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **crack-7z-hash** | Security | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |
| **train-fasttext** | ML | gpt-5.4-pro | 2-4 parallel | Task-native (from task.toml) | None (Stalemate exit) | `vm_goal_runs/<stamp>/results.json` | Haiku |

## 2. Infrastructure Setup & Sizing

- **Current VM Instance:** `harnesseng-regular-01` (`Standard_D4ds_v4` - 4 vCPU / 16 GB RAM) in Central US resource group `HARNESSENG-RG`.
- **Target Upgrade VM Instance:** Resizing `harnesseng-regular-01` to `Standard_D8ds_v4` (8 vCPU / 32 GB RAM) or `Standard_D16ds_v4` (16 vCPU / 64 GB RAM) before starting is recommended to allow safe parallel execution of 4 to 8 tasks.
- **Deallocation Responsibility:** Immediately after runs finish, execute `scripts/deallocate_harnesseng_vm.sh --resource-group HARNESSENG-RG --vm-name harnesseng-regular-01` to stop Azure VM billing.
- **Auto-Shutdown Schedule:** Verify/configure with `scripts/configure_harnesseng_vm_autoshutdown.sh` for UTC 23:00 to prevent runaway costs.

## 3. Haiku Monitoring Instructions

Haiku subagents are responsible for monitoring the runs in real-time. The monitoring protocol requires the following checks:
1. **Startup Check:** Verify that the run directory `vm_goal_runs/<stamp>` is created, and that the Docker container initializes successfully for each active task.
2. **Log Monitoring:** Tail the active run logs `/home/azureuser/harnesseng_vm/logs/<task_name>.log` to confirm the solver is actively executing steps.
3. **Step Budget Check:** Ensure that no task exceeds its maximum step limit or loops repeatedly on empty/stalemate submissions.
4. **Host Metrics:** Monitor VM CPU/Memory load to adjust concurrency dynamically if QEMU or heavy compilation tasks saturate the CPU.

## 4. Stop / Abort Criteria

An active run must be aborted immediately if any of the following occur:
- A task takes more than 10 consecutive steps with no new filesystem activity or command execution (stalemate loop).
- The Docker daemon within the VM becomes unresponsive or returns repeated daemon errors.
- Any critical command errors out due to out-of-memory (OOM) killer terminating processes on the VM.
- Azure billing threshold warning or quota errors occur.
