# Usage: make build push
DOCKER_USERNAME ?= tyzen9
APPLICATION_NAME ?= lftp-mirror
VERSION ?= 1.0.1
GIT_COMMIT ?= $(shell git rev-parse --short HEAD)
GIT_BRANCH ?= $(shell git rev-parse --abbrev-ref HEAD)
BUILD_DATE ?= $(shell date -u +'%Y-%m-%dT%H:%M:%SZ')

build:
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--tag ${DOCKER_USERNAME}/${APPLICATION_NAME}:${VERSION} \
		--tag ${DOCKER_USERNAME}/${APPLICATION_NAME}:latest \
		--build-arg VERSION=${VERSION} \
		--build-arg GIT_COMMIT=${GIT_COMMIT} \
		--build-arg BUILD_DATE=${BUILD_DATE} \
		--file .devcontainer/Dockerfile \
		--output type=oci,dest=./.local_build \
		.

push:
	docker buildx build \
		--platform linux/amd64,linux/arm64 \
		--tag ${DOCKER_USERNAME}/${APPLICATION_NAME}:${VERSION} \
		--tag ${DOCKER_USERNAME}/${APPLICATION_NAME}:latest \
		--build-arg VERSION=${VERSION} \
		--build-arg GIT_COMMIT=${GIT_COMMIT} \
		--build-arg BUILD_DATE=${BUILD_DATE} \
		--file .devcontainer/Dockerfile \
		--push \
		.