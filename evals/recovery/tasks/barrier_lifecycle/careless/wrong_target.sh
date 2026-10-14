#!/usr/bin/env bash
# expect: jobs_not_overlapped
# Copies the draft to a new module and leaves jobctl/runner.py untouched.
set -euo pipefail
cp jobctl/runner.py jobctl/runner_fixed.py
