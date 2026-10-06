#!/usr/bin/env bash
set -euo pipefail

ENGINE="${CONTAINER_ENGINE:-}"
if [[ -z "$ENGINE" ]]; then
  command -v podman >/dev/null 2>&1 && ENGINE=podman || ENGINE=docker
fi
command -v "$ENGINE" >/dev/null 2>&1 || { echo "no container engine available" >&2; exit 1; }

USERNS_ARGS=()
if [[ "$ENGINE" == podman ]]; then
  rootless="$("$ENGINE" info --format '{{.Host.Security.Rootless}}')"
  [[ "$rootless" != true ]] || USERNS_ARGS+=(--userns=keep-id)
fi

TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
mkdir -p "$TEST_DIR/state" "$TEST_DIR/secrets" "$TEST_DIR/workspace"
chmod 700 "$TEST_DIR/state" "$TEST_DIR/secrets"
printf 'smoke-secret\n' > "$TEST_DIR/secrets/anthropic_api_key"
chmod 600 "$TEST_DIR/secrets/anthropic_api_key"

run() {
  "$ENGINE" run --rm "${USERNS_ARGS[@]}" --workdir /workspace --read-only --tmpfs /tmp:exec,size=512m,mode=1777 \
    --cap-drop=ALL --security-opt=no-new-privileges \
    -v "$TEST_DIR/state:/app/.pi:rw,Z" -v "$TEST_DIR/secrets:/run/secrets:ro,Z" \
    -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest "$@"
}

version="$(run --version)"
expected_version="${PI_VERSION:-1.0.3}"
[[ "$version" == "$expected_version" ]] || { echo "expected Pi $expected_version, got $version" >&2; exit 1; }
run --offline --list-models >/dev/null
run --offline --version >/dev/null
"$ENGINE" run --rm --read-only --tmpfs /tmp:exec,size=512m,mode=1777 \
  --cap-drop=ALL --security-opt=no-new-privileges --entrypoint /usr/bin/python3 \
  "${USERNS_ARGS[@]}" -v "$TEST_DIR/state:/app/.pi:rw,Z" \
  -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest -c '
import os
from pathlib import Path
assert os.getuid() != 0
Path("/workspace/writable").touch()
assert os.access("/etc/passwd", os.R_OK)
try:
    Path("/root/forbidden").touch()
except OSError:
    pass
else:
    raise AssertionError("/root must not be writable")
'
test -e "$TEST_DIR/workspace/writable"
echo "smoke checks passed"
