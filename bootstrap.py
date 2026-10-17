#!/usr/bin/env python3
"""Enforce non-root execution and private file creation, then launch Pi."""

import os
import sys


def bootstrap(args: list[str], execvp=os.execvp) -> None:
    if os.geteuid() == 0:
        raise RuntimeError("Pi must not run as UID 0; use a non-root container user")
    os.umask(0o077)
    execvp("pi", ["pi", *args])


if __name__ == "__main__":
    bootstrap(sys.argv[1:])
