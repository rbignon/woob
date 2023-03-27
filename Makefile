# lint

.PHONY: lint cz isort flake8 hadolint mypy yamllint

lint: flake8 isort mypy yamllint

cz:
	cz check --rev-range 8ac4979095613577c3f7a7b9bea232a7ff4e000b..HEAD

isort:
	pre-commit run --all-files isort

flake8:
	pre-commit run --all-files flake8

mypy:
	pre-commit run --all-files mypy

yamllint:
	pre-commit run --all-files yamllint

# documentation

.PHONY: docs

docs:
	$(MAKE) -C docs html

# deps

.PHONY: sync-deps

all-requirements.txt: pyproject.toml
	pip install -U pip-tools
	pip-compile --resolver=backtracking --no-emit-index-url -o all-requirements.txt pyproject.toml requirements-dev.txt

sync-deps: all-requirements.txt
	pip install -U pip-tools
	pip-sync all-requirements.txt
