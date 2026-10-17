#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import bootstrap


def test_bootstrap_executes_pi() -> None:
    events = []
    with patch.object(bootstrap.os, "geteuid", return_value=1000), patch.object(bootstrap.os, "umask") as umask:
        bootstrap.bootstrap(["--version"], execvp=lambda program, args: events.append((program, args)))
        umask.assert_called_once_with(0o077)
    assert events == [("pi", ["pi", "--version"])]


def test_root_is_rejected_before_exec() -> None:
    with patch.object(bootstrap.os, "geteuid", return_value=0):
        events = []
        try:
            bootstrap.bootstrap([], execvp=lambda *args: events.append(args))
        except RuntimeError as error:
            assert "UID 0" in str(error)
        else:
            raise AssertionError("expected UID 0 rejection")
        assert events == []


def test_private_file_creation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        previous = os.umask(0o022)
        try:
            with patch.object(bootstrap.os, "geteuid", return_value=1000):
                def create_state(*args):
                    (root / "auth.json").write_text("{}")
                    (root / "sessions").mkdir()
                bootstrap.bootstrap([], execvp=create_state)
            assert (root / "auth.json").stat().st_mode & 0o777 == 0o600
            assert (root / "sessions").stat().st_mode & 0o777 == 0o700
        finally:
            os.umask(previous)


if __name__ == "__main__":
    test_bootstrap_executes_pi()
    test_root_is_rejected_before_exec()
    test_private_file_creation()
    print("bootstrap checks passed")
