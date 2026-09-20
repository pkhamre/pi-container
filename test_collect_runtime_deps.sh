#!/usr/bin/env bash
set -euo pipefail
ROOTFS="$(mktemp -d)"
trap 'rm -rf "$ROOTFS"' EXIT
scripts/collect-runtime-deps.sh "$ROOTFS" /bin/true sh
[ -e "$ROOTFS/bin/true" ]
[ -L "$ROOTFS/bin/sh" ]
target="$(readlink "$ROOTFS/bin/sh")"
[ -x "$ROOTFS$target" ]
if scripts/collect-runtime-deps.sh "$ROOTFS/missing" does-not-exist; then
  echo "expected missing executable to fail" >&2
  exit 1
fi
echo "runtime collector checks passed"
