#!/usr/bin/env bash
# CI wrapper: runs the simulator and keeps the last lines for the job log.
python3 build/simulate_build.py 2>&1 | tail -n 5
