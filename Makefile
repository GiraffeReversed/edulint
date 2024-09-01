EDULINT_PATH = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
EDULINT_VENV_PATH = ${EDULINT_PATH}/.venv

DATA_PATH = ${EDULINT_PATH}../data
LINTINGS_PATH = ${EDULINT_PATH}../lintings

.PHONY: all dist mypy test check run setup clean

all: setup dist check

setup: requirements.txt requirements.dev.txt tests/requirements.txt
	python3 -m venv ${EDULINT_VENV_PATH} && \
	. ${EDULINT_VENV_PATH}/bin/activate && \
	python3 -m pip install --upgrade pip && \
	python3 -m pip install --upgrade -r requirements.txt -r requirements.dev.txt -r tests/requirements.txt

clean:
	rm -rf __pycache__ edulint.egg-info .mypy_cache .venv dist

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
		python3 -m pytest -n4 -k "${ARGS}" ${EDULINT_PATH}/tests/

cov:
	. ${EDULINT_VENV_PATH}/bin/activate && \
		export PYTHONPATH=${EDULINT_PATH} && \
		python3 -m pytest -n8 --cov-report html  --cov=edulint ${EDULINT_PATH}/tests/

check: mypy test

run:
	export PYTHONPATH=${EDULINT_PATH} && \
		python3 -m edulint check --disable-version-check --disable-explanations-update ${ARGS}

perf:
	export PYTHONPATH=${EDULINT_PATH} && \
		time py-spy record -s -n -r1000 -o profile.ss -f speedscope -- \
		python3 -m edulint check \
		--disable-version-check --disable-explanations-update \
		-o ignore-infile-config-for=edulint \
		${ARGS} \
		> /dev/null \
		&& code profile.ss

lint_data:
	DATA_DIR=${DATA_PATH}/${YEAR}; \
	LINTINGS_DIR=${LINTINGS_PATH}/${YEAR}/edulint-${VERSION}; \
	if [ -z "${JSON}" ]; then \
		EXT=txt; \
	else \
		EXT=json; \
		EXTRA=--json; \
	fi; \
	mkdir -p $$LINTINGS_DIR; \
	for week in `ls $$DATA_DIR`; do \
		echo $$week; \
		export PYTHONPATH=${EDULINT_PATH} && \
			python3 -m edulint check -o "${OPTIONS}" $$EXTRA $$DATA_DIR/$$week/*.py > $$LINTINGS_DIR/$$week.$$EXT; \
	done;

