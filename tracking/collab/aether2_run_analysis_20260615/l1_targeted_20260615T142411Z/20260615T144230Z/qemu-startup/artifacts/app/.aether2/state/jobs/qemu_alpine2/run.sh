#!/usr/bin/env sh
set +e
cd "/app"
trap 'status=$?; if [ ! -f "/app/.aether2/state/jobs/qemu_alpine2/exit_code" ]; then printf "%s\\n" "$status" > "/app/.aether2/state/jobs/qemu_alpine2/exit_code"; fi' EXIT
. "/app/.aether2/state/jobs/qemu_alpine2/command.sh" >> "/app/.aether2/state/jobs/qemu_alpine2/job.log" 2>&1
code=$?
printf "%s\n" "$code" > "/app/.aether2/state/jobs/qemu_alpine2/exit_code"
exit "$code"
