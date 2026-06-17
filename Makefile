PY ?= python3.11

.PHONY: test

test:
	$(PY) -m pytest -q
