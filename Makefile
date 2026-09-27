.PHONY: help setup fetch build check test lint types docs site site-build site-types clean \
	site-pages deploy mirror-pull mirror-push

help:
	@echo "make setup       install Python and site dependencies"
	@echo "make fetch       download catalog documents, verified against the lock files"
	@echo "make build       read, assemble, check and publish the dataset"
	@echo "make check       lint, type-check and test everything"
	@echo "make docs        regenerate docs/schema.md"
	@echo "make site        run the website locally (after make build)"
	@echo "make site-build  build the static website into site/dist"
	@echo "make deploy      publish the site and downloads (after make build; see README)"

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

# Deployment: the site on Cloudflare Pages; the downloads, and a private mirror of the document
# store, in Cloudflare R2 buckets used through its S3 API. Needs CLOUDFLARE_ACCOUNT_ID, R2 keys
# as AWS credentials, and DOWNLOADS_URL, where the downloads bucket is served.
PAGES_PROJECT ?= splits
STORE_BUCKET ?= splits-documents
DOWNLOADS_BUCKET ?= splits-downloads
R2 = $(if $(CLOUDFLARE_ACCOUNT_ID),,$(error set CLOUDFLARE_ACCOUNT_ID)) \
	aws s3 --endpoint-url https://$(CLOUDFLARE_ACCOUNT_ID).r2.cloudflarestorage.com --region auto

# The site as Pages serves it: without 404.html, so every path gets the app with a 200, and
# without the downloads, which exceed the 25 MiB Pages allows a file.
site-pages:
	$(if $(DOWNLOADS_URL),,$(error set DOWNLOADS_URL to where the downloads are served))
	VITE_DOWNLOADS_URL=$(DOWNLOADS_URL) npm --prefix site run build
	rm -rf site/dist/404.html site/dist/data/downloads

# Downloads first, so the new site never links to files that are not there yet.
deploy: site-pages
	$(R2) sync site/public/data/downloads s3://$(DOWNLOADS_BUCKET) --delete --only-show-errors \
		--content-disposition attachment --cache-control "public, max-age=300"
	npx --yes wrangler@4 pages deploy site/dist --project-name $(PAGES_PROJECT) --branch main

# The store is content-addressed, so syncing only ever adds files.
mirror-pull:
	$(R2) sync s3://$(STORE_BUCKET) data/store --only-show-errors

mirror-push:
	$(R2) sync data/store s3://$(STORE_BUCKET) --only-show-errors

clean:
	rm -rf build data/cache site/dist
