#!/usr/bin/env bash
set -euo pipefail
export PIDS_LIMIT=256

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT
mkdir -p "$TEST_DIR/bin" "$TEST_DIR/home" "$TEST_DIR/workspace"
printf '%s\n' '[user]' '  name = Test User' '  email = test@example.com' > "$TEST_DIR/home/.gitconfig"
mkdir -p "$TEST_DIR/home/.kube"
printf '%s\n' 'apiVersion: v1' > "$TEST_DIR/home/.kube/config"
mkdir -p "$TEST_DIR/home/.config/git"
printf '%s\n' '[user]' '  signingkey = test-key' > "$TEST_DIR/home/.config/git/config"

cat > "$TEST_DIR/bin/podman" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == info ]]; then
  echo true
  exit 0
fi
printf '%s\n' "$@" > "$ARGS_FILE"
umask > "$ARGS_FILE.umask"
EOF
cat > "$TEST_DIR/bin/docker" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$@" > "$ARGS_FILE"
umask > "$ARGS_FILE.umask"
EOF
chmod +x "$TEST_DIR/bin/podman" "$TEST_DIR/bin/docker"

ARGS_FILE="$TEST_DIR/args" HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" \
  PI_WORKSPACE="$TEST_DIR/workspace" "$ROOT_DIR/bin/pi-container" --memory 2g --cpus 2 --pids-limit 512 --host-access \
  --version "quoted argument"

grep -Fx -- 'run' "$TEST_DIR/args"
grep -F -- "$TEST_DIR/home/.pi-container/state:/app/.pi:rw,Z" "$TEST_DIR/args"
grep -F -- "$TEST_DIR/home/.pi-container/secrets:/run/secrets:ro,Z" "$TEST_DIR/args"
grep -F -- "$TEST_DIR/workspace:/workspace:rw,Z" "$TEST_DIR/args"
grep -F -- "$TEST_DIR/home/.gitconfig:/app/.gitconfig:ro,Z" "$TEST_DIR/args"
grep -F -- "$TEST_DIR/home/.config/git/config:/app/.config/git/config:ro,Z" "$TEST_DIR/args"
grep -F -- "$TEST_DIR/home/.kube/config:/run/kubeconfig:ro,Z" "$TEST_DIR/args"
grep -Fx -- 'KUBECONFIG=/run/kubeconfig' "$TEST_DIR/args"
grep -Fx -- '--read-only' "$TEST_DIR/args"
grep -F -- '--tmpfs' "$TEST_DIR/args"
grep -Fx -- '--cap-drop=ALL' "$TEST_DIR/args"
grep -Fx -- '--security-opt=no-new-privileges' "$TEST_DIR/args"
grep -Fx -- '--memory=2g' "$TEST_DIR/args"
grep -Fx -- '--cpus=2' "$TEST_DIR/args"
grep -Fx -- '--pids-limit=512' "$TEST_DIR/args"
grep -Fx -- '--ulimit' "$TEST_DIR/args"
grep -Fx -- 'core=0' "$TEST_DIR/args"
grep -Fx -- '0077' "$TEST_DIR/args.umask"
grep -Fx -- '--userns=keep-id' "$TEST_DIR/args"
grep -F -- 'host.containers.internal:host-gateway' "$TEST_DIR/args"
if grep -Fxq -- '--yolo' "$TEST_DIR/args"; then
  echo "launcher must not inject --yolo" >&2
  exit 1
fi
grep -Fx -- '--version' "$TEST_DIR/args"
grep -Fx -- 'quoted argument' "$TEST_DIR/args"

if HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" PI_WORKSPACE="$TEST_DIR/workspace" \
  "$ROOT_DIR/bin/pi-container" --memory >/dev/null 2>&1; then
  echo "expected missing --memory value to fail" >&2
  exit 1
fi

if HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" PI_WORKSPACE="$TEST_DIR/workspace" \
  HTTPS_PROXY='http://user:password@example.test:8080' "$ROOT_DIR/bin/pi-container" >/dev/null 2>&1; then
  echo "expected proxy credentials to fail" >&2
  exit 1
fi

ARGS_FILE="$TEST_DIR/docker-args" HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" \
  CONTAINER_ENGINE=docker PI_WORKSPACE="$TEST_DIR/workspace" "$ROOT_DIR/bin/pi-container" --version
grep -Fx -- '--read-only' "$TEST_DIR/docker-args"
grep -Fx -- '--pids-limit=256' "$TEST_DIR/docker-args"
grep -Fx -- 'core=0' "$TEST_DIR/docker-args"
if HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" PI_WORKSPACE="$TEST_DIR/not-a-directory" \
  "$ROOT_DIR/bin/pi-container" >/dev/null 2>&1; then
  echo "expected invalid workspace to fail" >&2
  exit 1
fi

expect_launcher_failure() {
  local expected="$1" output
  shift
  rm -f "$TEST_DIR/rejected-args"
  if output="$(ARGS_FILE="$TEST_DIR/rejected-args" HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" \
    PI_WORKSPACE="$TEST_DIR/workspace" "$ROOT_DIR/bin/pi-container" "$@" 2>&1)"; then
    echo "expected launcher validation to fail: $*" >&2
    exit 1
  fi
  [[ ! -e "$TEST_DIR/rejected-args" && "$output" == *"$expected"* ]] || {
    echo "expected rejection before engine run ($expected), got: $output" >&2
    exit 1
  }
}
for invalid in 0 -1 1.5 invalid ""; do
  expect_launcher_failure "must be a positive integer" --pids-limit "$invalid"
done
for option in --pids-limit; do
  expect_launcher_failure "$option requires" "$option"
done
ARGS_FILE="$TEST_DIR/env-pids-args" HOME="$TEST_DIR/home" PATH="$TEST_DIR/bin:$PATH" \
  PIDS_LIMIT=300 PI_WORKSPACE="$TEST_DIR/workspace" "$ROOT_DIR/bin/pi-container" --version
grep -Fx -- '--pids-limit=300' "$TEST_DIR/env-pids-args"
PIDS_LIMIT=invalid expect_launcher_failure "must be a positive integer"

echo "launcher checks passed"
