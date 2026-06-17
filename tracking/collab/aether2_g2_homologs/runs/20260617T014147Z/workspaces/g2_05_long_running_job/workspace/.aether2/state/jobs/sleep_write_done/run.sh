#!/usr/bin/env sh
set +e
cd "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace"
trap 'status=$?; if [ ! -f "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace/.aether2/state/jobs/sleep_write_done/exit_code" ]; then printf "%s\\n" "$status" > "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace/.aether2/state/jobs/sleep_write_done/exit_code"; fi' EXIT
. "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace/.aether2/state/jobs/sleep_write_done/command.sh" >> "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace/.aether2/state/jobs/sleep_write_done/job.log" 2>&1
code=$?
printf "%s\n" "$code" > "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_05_long_running_job/workspace/.aether2/state/jobs/sleep_write_done/exit_code"
exit "$code"
