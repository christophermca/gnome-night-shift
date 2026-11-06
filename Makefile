PROJECT_NAME := gnome-night-shift
CORE_NAME    := nocturne-shift
NOCTURNE_SHIFT ?= $(CORE_NAME)
GNOME_NIGHT_SHIFT ?= $(PROJECT_NAME)
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

.PHONY: dev test test-nocov build rebuild publish-testpypi testpypi-wheels install-dependencies install-global install-dev upgrade-dev

testpypi-wheels: $(PY)
	rm -rf $(WHEELS)
	$(PY) -m pip download --no-deps --only-binary=:all: \
		--index-url $(TESTPYPI) --dest $(WHEELS) \
		"$(NOCTURNE_SHIFT)" "$(GNOME_NIGHT_SHIFT)"

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

# Install the downloaded wheel file; its dependencies come from PyPI only
install-dependencies: testpypi-wheels
	$(PY) -m pip install $(WHEELS)/nocturne_shift-*.whl

# The core first, then install **this** package into its venv: installing this
# package on its own would look up nocturne-shift by name on PyPI.
install-global: testpypi-wheels
	sudo pipx install --global --system-site-packages $(abspath $(WHEELS))/nocturne_shift-*.whl
	sudo pipx install --global nocturne-shift $(abspath $(WHEELS))/gnome_night_shift-*.whl

install-dev: dev

upgrade-dev: $(PY)
	$(PY) -m pip install --upgrade .
