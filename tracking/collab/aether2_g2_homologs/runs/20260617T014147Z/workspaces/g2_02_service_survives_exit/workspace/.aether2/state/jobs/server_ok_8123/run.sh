#!/usr/bin/env sh
set +e
cd "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace"
trap 'status=$?; if [ ! -f "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace/.aether2/state/jobs/server_ok_8123/exit_code" ]; then printf "%s\\n" "$status" > "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace/.aether2/state/jobs/server_ok_8123/exit_code"; fi' EXIT
. "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace/.aether2/state/jobs/server_ok_8123/command.sh" >> "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace/.aether2/state/jobs/server_ok_8123/job.log" 2>&1
code=$?
printf "%s\n" "$code" > "/Users/mohamud/Downloads/harnesseng/tracking/collab/aether2_g2_homologs/runs/20260617T014147Z/workspaces/g2_02_service_survives_exit/workspace/.aether2/state/jobs/server_ok_8123/exit_code"
exit "$code"
