#!/usr/bin/env sh
set +e
cd "/app"
trap 'status=$?; if [ ! -f "/app/.aether2/state/jobs/qemu_alpine/exit_code" ]; then printf "%s\\n" "$status" > "/app/.aether2/state/jobs/qemu_alpine/exit_code"; fi' EXIT
. "/app/.aether2/state/jobs/qemu_alpine/command.sh" >> "/app/.aether2/state/jobs/qemu_alpine/job.log" 2>&1
code=$?
printf "%s\n" "$code" > "/app/.aether2/state/jobs/qemu_alpine/exit_code"
exit "$code"
