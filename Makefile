all: docker

docker:
	docker build -t multifoundry:latest .
