.PHONY: build build-builder-tools build-latest shell test smoke clean prune-cache

ENGINE ?= $(shell command -v podman >/dev/null 2>&1 && echo podman || echo docker)
USER_UID := $(shell id -u)
USER_GID := $(shell id -g)
PI_VERSION ?= 1.0.3
NODE_MAJOR ?= 24
NPM_VERSION ?= 12.2.0

BUILD_ARGS = --build-arg USER_UID=$(USER_UID) --build-arg USER_GID=$(USER_GID) --build-arg PI_VERSION=$(PI_VERSION) --build-arg NODE_MAJOR=$(NODE_MAJOR) --build-arg NPM_VERSION=$(NPM_VERSION)

build:
	@set -eu; created_ca=0; \
	if [ ! -e custom-ca.crt ]; then touch custom-ca.crt; created_ca=1; fi; \
	trap '[ "$$created_ca" -eq 0 ] || rm -f custom-ca.crt' EXIT; \
	$(ENGINE) build $(BUILD_ARGS) -t pi-container:latest .

build-builder-tools:
	@set -eu; created_ca=0; \
	if [ ! -e custom-ca.crt ]; then touch custom-ca.crt; created_ca=1; fi; \
	trap '[ "$$created_ca" -eq 0 ] || rm -f custom-ca.crt' EXIT; \
	$(ENGINE) build $(BUILD_ARGS) --target builder-tools -t pi-container:builder-tools .

build-latest:
	@set -eu; version=$$(curl -fsSL https://registry.npmjs.org/%40earendil-works%2Fpi-coding-agent/latest | python3 -c 'import json, sys; print(json.load(sys.stdin)["version"])'); test -n "$$version"; $(MAKE) build PI_VERSION=$$version

shell: build-builder-tools
	mkdir -p homebase workspace secrets
	$(ENGINE) run --rm -it --workdir /workspace --read-only --tmpfs /tmp:exec,size=512m,mode=1777 --cap-drop=ALL --security-opt=no-new-privileges -v $(PWD)/homebase:/app:rw,Z -v $(PWD)/workspace:/workspace:rw,Z -v $(PWD)/secrets:/run/secrets:ro,Z --entrypoint /bin/bash pi-container:builder-tools

test:
	./test_bootstrap.py
	./test_launcher.sh
	python3 test_build_config.py
	python3 test_collector.py
	./test_collect_runtime_deps.sh

smoke: build
	CONTAINER_ENGINE=$(ENGINE) PI_VERSION=$(PI_VERSION) ./test_smoke.sh

clean:
	$(ENGINE) rmi pi-container:latest pi-container:builder-tools || true

prune-cache:
	$(ENGINE) builder prune -f
