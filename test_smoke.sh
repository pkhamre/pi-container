#!/usr/bin/env bash
set -euo pipefail

ENGINE="${CONTAINER_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  command -v podman >/dev/null 2>&1 && ENGINE=podman || ENGINE=docker
fi
command -v "$ENGINE" >/dev/null 2>&1 || { echo "no container engine available" >&2; exit 1; }

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
mkdir -p "$TEST_DIR/state" "$TEST_DIR/secrets" "$TEST_DIR/workspace"
chmod 700 "$TEST_DIR/state" "$TEST_DIR/secrets"
printf 'smoke-secret\n' > "$TEST_DIR/secrets/anthropic_api_key"
chmod 600 "$TEST_DIR/secrets/anthropic_api_key"

run() {
  "$ENGINE" run --rm --workdir /workspace --read-only --tmpfs /tmp:exec,size=512m,mode=1777 \
    --cap-drop=ALL --security-opt=no-new-privileges \
    -v "$TEST_DIR/state:/app/.pi:rw,Z" -v "$TEST_DIR/secrets:/run/secrets:ro,Z" \
    -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest "$@"
}

version="$(run --version)"
[[ "$version" == 0.86.1 ]]
run --list-models >/dev/null
run --offline --no-session --print --no-tools "" >/dev/null 2>&1 || true

run --version >/dev/null
"$ENGINE" run --rm --entrypoint /bin/sh -v "$TEST_DIR/state:/app/.pi:rw,Z" \
  -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest \
  -c 'test "$(id -u)" -ne 0; test -w /workspace; touch /workspace/writable; ! touch /root/forbidden; test -r /etc/passwd'
test -e "$TEST_DIR/workspace/writable"
test -d "$TEST_DIR/state/agent" || test -d "$TEST_DIR/state/.pi/agent" || test -d "$TEST_DIR/state"
echo "smoke checks passed"
