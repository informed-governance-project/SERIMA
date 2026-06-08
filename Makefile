SHELL := /bin/bash

VERSION?=$(shell git describe --exact-match --tags 2>/dev/null || echo "latest" )
IMAGE?=local/serima

.PHONY: image

# target: all - Default target. Does nothing.
all:
	@echo "Hello $(LOGNAME), nothing to do by default."
	@echo "Try 'make help'"

help:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

activate:
	poetry shell

run:
	python manage.py runserver

migration:
	python manage.py makemigrations

migrate:
	python manage.py migrate

superuser:
	python manage.py createsuperuser

models:
	python manage.py graph_models governanceplatform incidents --pydot -g -o docs/_static/app-models.png

openapi:
	python manage.py spectacular --format openapi > docs/_static/openapi.yml

generatepot:
	python manage.py makemessages -a --keep-pot

update:
	npm ci
	poetry install --only main
	python manage.py collectstatic
	python manage.py compilemessages
	python manage.py migrate

clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

image:
	docker build -f docker/Dockerfile --build-arg APP_VERSION=$(shell git describe --tags) -t $(IMAGE):$(VERSION) .
