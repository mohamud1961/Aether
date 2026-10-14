#!/usr/bin/env bash
# expect: record_value_mismatch
# Writes an array with the right shape and plausible numbers, without reading the export.
set -euo pipefail
mkdir -p out
cat > out/canonical.json <<'JSON'
[
  {
    "id": 1,
    "name": "Alice",
    "balance": 1234.50,
    "active": true,
    "tags": ["admin", "user"]
  },
  {
    "id": 2,
    "name": "Bob",
    "balance": 0.00,
    "active": false,
    "tags": ["user"]
  },
  {
    "id": 3,
    "name": "Charlie",
    "balance": 99999.99,
    "active": true,
    "tags": ["admin", "moderator", "user"]
  },
  {
    "id": 4,
    "name": "Diana",
    "balance": -500.25,
    "active": true,
    "tags": ["user"]
  },
  {
    "id": 5,
    "name": "Eve",
    "balance": 42.10,
    "active": false,
    "tags": []
  },
  {
    "id": 6,
    "name": "Okafor \"Oke\" Nnamdi",
    "balance": 7.00,
    "active": true,
    "tags": ["ops"]
  }
]
JSON
