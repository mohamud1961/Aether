#!/usr/bin/env bash
# boot wrapper: the loader reads CONFIG, defaulting to the release config
CONFIG="${CONFIG:-app/config/service.yaml}"
echo "loading $CONFIG"
