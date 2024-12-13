all: build

build:
	docker compose build

up: build
	docker compose up -d

lint: install-linters lint-imports lint-code

install-linters:
	poetry install --with=lint

lint-imports:
	poetry run isort .

lint-code:
	poetry run black .
