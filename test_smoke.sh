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
    --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=256 --ulimit core=0 \
    -v "$TEST_DIR/state:/app/.pi:rw,Z" -v "$TEST_DIR/secrets:/run/secrets:ro,Z" \
    -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest "$@"
}

version="$(run --version)"
expected_version="${PI_VERSION:-1.0.3}"
[[ "$version" == "$expected_version" ]] || { echo "expected Pi $expected_version, got $version" >&2; exit 1; }
run --offline --list-models >/dev/null
run --offline --version >/dev/null
"$ENGINE" run --rm --read-only --tmpfs /tmp:exec,size=512m,mode=1777 \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=256 --ulimit core=0 \
  --entrypoint /usr/bin/python3 \
  "${USERNS_ARGS[@]}" -v "$TEST_DIR/state:/app/.pi:rw,Z" \
  -v "$TEST_DIR/workspace:/workspace:rw,Z" pi-container:latest -c '
import os
import resource
import runpy
from pathlib import Path
assert os.getuid() != 0
assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
for pids_path in ("/sys/fs/cgroup/pids.max", "/sys/fs/cgroup/pids/pids.max"):
    if Path(pids_path).is_file():
        assert Path(pids_path).read_text().strip() == "256"
        break
else:
    raise AssertionError("cannot verify the cgroup process limit")
# Exercise the real bootstrap without launching Pi, then check inherited modes.
runpy.run_path("/usr/local/bin/bootstrap.py")["bootstrap"]([], execvp=lambda *args: None)
assert os.umask(0o077) == 0o077
private_file = Path("/app/.pi/private-file")
private_file.write_text("test")
private_dir = Path("/app/.pi/private-directory")
private_dir.mkdir()
assert private_file.stat().st_mode & 0o777 == 0o600
assert private_dir.stat().st_mode & 0o777 == 0o700
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
if root_output="$("$ENGINE" run --rm "${USERNS_ARGS[@]}" --user 0:0 --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges --pids-limit=256 --ulimit core=0 \
  pi-container:latest --offline --version 2>&1)"; then
  echo "expected container startup as UID 0 to fail" >&2
  exit 1
fi
[[ "$root_output" == *"UID 0"* ]] || { echo "unexpected root startup failure: $root_output" >&2; exit 1; }
echo "smoke checks passed"
