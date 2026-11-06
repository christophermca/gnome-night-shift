PROJECT_NAME := gnome-night-shift
CORE_NAME    := nocturne-shift
# Local checkout of the core, for `make dev` (override: make dev CORE_DIR=...)
CORE_DIR     ?= ../nocturne-shift
INDEXES      := --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/
VENV         := venv
PYTHON       ?= python3
PY           := $(VENV)/bin/python

# Each recipe line runs in its own shell, so `. venv/bin/activate` can't carry
# over to other targets. Call the venv's python directly instead.
# --system-site-packages reuses the distro's PyGObject/pycairo (building them
# with pip needs the C headers for cairo and gobject-introspection).
$(PY):
	$(PYTHON) -m venv --system-site-packages $(VENV)
	$(PY) -m pip install -U pip

.PHONY: dev test test-nocov build rebuild publish-testpypi install-dependencies install-global install-dev upgrade-dev

# nocturne-shift>=0.5.0 isn't on PyPI yet, so install the core from CORE_DIR.
dev: $(PY)
	$(PY) -m pip install -e "$(CORE_DIR)"
	$(PY) -m pip install -e ".[test,dev]"

test: dev
	$(PY) -m pytest -c pytest.ini

test-nocov: dev
	$(PY) -m pytest -c pytest.ini --no-cov

build: $(PY)
	$(PY) -m pip install -U build
	$(PY) -m build . --outdir dist/

rebuild:
	rm -rf dist/
	$(MAKE) build

publish-testpypi: rebuild
	$(PY) -m pip install -U twine
	$(PY) -m twine upload --repository testpypi dist/*

install-dependencies:
	$(PY) -m pip install $(INDEXES) $(CORE_NAME)

install-global:
	sudo pipx install --global --system-site-packages --pip-args="$(INDEXES)" $(PROJECT_NAME)    # pulls in nocturne-shift

install-dev: dev

upgrade-dev: $(PY)
	$(PY) -m pip install --upgrade .
