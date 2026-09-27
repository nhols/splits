.PHONY: help setup fetch build check test lint types docs site site-build site-types clean

help:
	@echo "make setup       install Python and site dependencies"
	@echo "make fetch       download catalog documents, verified against the lock files"
	@echo "make build       read, assemble, check and publish the dataset"
	@echo "make check       lint, type-check and test everything"
	@echo "make docs        regenerate docs/schema.md"
	@echo "make site        run the website locally (after make build)"
	@echo "make site-build  build the static website into site/dist"

setup:
	uv sync
	npm --prefix site ci

fetch:
	uv run splits fetch

build:
	uv run splits build

check: lint types test
	npm --prefix site run typecheck
	npm --prefix site test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

types:
	uv run mypy

test:
	uv run pytest

docs:
	uv run splits schema --output docs/schema.md

site-types:
	npm --prefix site run types

site:
	npm --prefix site run dev

site-build:
	npm --prefix site run build

clean:
	rm -rf build data/cache site/dist
