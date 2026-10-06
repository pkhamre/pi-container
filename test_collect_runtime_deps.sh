#!/usr/bin/env bash
set -euo pipefail
ROOTFS="$(mktemp -d)"
trap 'rm -rf "$ROOTFS"' EXIT
scripts/collect-runtime-deps.sh "$ROOTFS" /bin/true sh
# Before usr-merge, a relative /bin alias may only resolve under /usr/bin.
# Verify both the requested entry and its independently collected real target.
[ -e "$ROOTFS/bin/true" ] || [ -L "$ROOTFS/bin/true" ]
true_target="$(readlink -f /bin/true)"
[ -x "$ROOTFS$true_target" ] || { echo "missing true target: $true_target" >&2; exit 1; }
[ -L "$ROOTFS/bin/sh" ]
target="$(readlink "$ROOTFS/bin/sh")"
[ -x "$ROOTFS$target" ]
if scripts/collect-runtime-deps.sh "$ROOTFS/missing" does-not-exist; then
  echo "expected missing executable to fail" >&2
  exit 1
fi
echo "runtime collector checks passed"
