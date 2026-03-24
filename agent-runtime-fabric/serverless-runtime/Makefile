PYTHON ?= python3

.PHONY: test smoke lint

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py'

lint:
	PYTHONPATH=src $(PYTHON) -m py_compile src/runtime_fabric.py tests/test_runtime_fabric.py

smoke:
	printf '%s\n' '{"tool":"run_code","session_id":"smoke","args":{"language":"python","code":"print(2+2)"}}' | PYTHONPATH=src $(PYTHON) src/runtime_fabric.py
