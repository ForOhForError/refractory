all: build

build:
	docker compose build

up: build
	docker compose up -d

lint:
	poetry install --with=lint
	poetry run isort .
	poetry run black .
