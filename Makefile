PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest
SMOKE_OUTPUT_ROOT ?= /private/tmp/harnesseng_public_manifest_smoke

.PHONY: help public-cold-start public-smoke public-tests public-readiness

help:
	@printf '%s\n' \
		'public-cold-start  Run the public provenance sweep and launch-integrity preflight' \
		'public-smoke       Run the synthetic public manifest repair smoke pack' \
		'public-tests       Run the focused public-readiness pytest slice' \
		'public-readiness   Run cold-start, smoke, and focused tests'

public-cold-start:
	bash scripts/public_readiness_cold_start.sh

public-smoke:
	bash scripts/public_manifest_repair_smoke.sh "$(SMOKE_OUTPUT_ROOT)"

public-tests:
	$(PYTEST) tests/test_public_manifest_repair_smoke.py

public-readiness: public-tests public-cold-start public-smoke
