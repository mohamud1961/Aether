PY ?= python3.11

.PHONY: test deps gates check

test:
	$(PY) -m pytest -q

deps:
	$(PY) tools/check_imports.py

gates:
	$(PY) -m harness_evals validate-graders evals
	$(PY) tools/check_tasks.py evals

check: deps test gates
