EDULINT_PATH = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EDULINT_VENV_PATH = ${EDULINT_PATH}/.venv

.PHONY: all dist mypy test check run

all: dist check

dist:
	python3 -m build ${EDULINT_PATH}
	. ${EDULINT_VENV_PATH}/bin/activate && \
		python3 -m pip install --upgrade ${EDULINT_PATH}

mypy:
	export MYPYPATH=${EDULINT_PATH} && \
		mypy ${EDULINT_PATH}/edulint --strict && \
		mypy ${EDULINT_PATH}/tests/*.py

test:
	. ${EDULINT_VENV_PATH}/bin/activate && \
		export PYTHONPATH=${EDULINT_PATH} && \
		python3 -m pytest -k "${ARGS}" ${EDULINT_PATH}/tests/

check: mypy test

run:
	export PYTHONPATH=${EDULINT_PATH} && \
		python3 -m edulint ${ARGS}
