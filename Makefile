PY ?= python3.11

.PHONY: test deps check

test:
	$(PY) -m pytest -q

deps:
	$(PY) tools/check_imports.py

check: deps test
