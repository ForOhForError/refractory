all: build

build: tailwind
	docker compose build

up: build
	docker compose up -d

tailwind:
	npm run gencss