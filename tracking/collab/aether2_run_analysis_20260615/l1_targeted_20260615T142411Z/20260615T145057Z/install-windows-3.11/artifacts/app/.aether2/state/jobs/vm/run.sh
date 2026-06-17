#!/usr/bin/env sh
set +e
cd "/app"
trap 'status=$?; if [ ! -f "/app/.aether2/state/jobs/vm/exit_code" ]; then printf "%s\\n" "$status" > "/app/.aether2/state/jobs/vm/exit_code"; fi' EXIT
. "/app/.aether2/state/jobs/vm/command.sh" >> "/app/.aether2/state/jobs/vm/job.log" 2>&1
code=$?
printf "%s\n" "$code" > "/app/.aether2/state/jobs/vm/exit_code"
exit "$code"
