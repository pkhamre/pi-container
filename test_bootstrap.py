#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import bootstrap


def test_values_and_path_secrets() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "anthropic_api_key").write_text("secret\n", encoding="utf-8")
        (root / "google_application_credentials").write_text("{}", encoding="utf-8")
        (root / "custom_ca_certificate").write_text("certificate", encoding="utf-8")
        env = {}
        bootstrap.load_secrets(root, env)
        assert env["ANTHROPIC_API_KEY"] == "secret"
        assert env["GOOGLE_APPLICATION_CREDENTIALS"] == str(root / "google_application_credentials")
        assert env["NODE_EXTRA_CA_CERTS"] == str(root / "custom_ca_certificate")


def test_unsupported_files_are_ignored() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "PATH").write_text("bad", encoding="utf-8")
        bootstrap.load_secrets(root, {})


def test_symlink_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "target"
        target.write_text("secret", encoding="utf-8")
        (root / "openai_api_key").symlink_to(target)
        try:
            bootstrap.load_secrets(root, {})
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected symlink rejection")


def test_bootstrap_executes_pi() -> None:
    events = []
    original = bootstrap.load_secrets
    bootstrap.load_secrets = lambda: events.append("secrets")
    try:
        with patch.object(bootstrap.os, "geteuid", return_value=1000), patch.object(bootstrap.os, "umask") as umask:
            bootstrap.bootstrap(["--version"], execvp=lambda program, args: events.append((program, args)))
            umask.assert_called_once_with(0o077)
    finally:
        bootstrap.load_secrets = original
    assert events == ["secrets", ("pi", ["pi", "--version"])]


def test_root_is_rejected_before_secrets_or_exec() -> None:
    with patch.object(bootstrap.os, "geteuid", return_value=0), patch.object(bootstrap, "load_secrets") as secrets:
        events = []
        try:
            bootstrap.bootstrap([], execvp=lambda *args: events.append(args))
        except RuntimeError as error:
            assert "UID 0" in str(error)
        else:
            raise AssertionError("expected UID 0 rejection")
        secrets.assert_not_called()
        assert events == []


def test_private_file_creation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        previous = os.umask(0o022)
        try:
            with patch.object(bootstrap.os, "geteuid", return_value=1000), patch.object(bootstrap, "load_secrets"):
                def create_state(*args):
                    (root / "auth.json").write_text("{}")
                    (root / "sessions").mkdir()
                bootstrap.bootstrap([], execvp=create_state)
            assert (root / "auth.json").stat().st_mode & 0o777 == 0o600
            assert (root / "sessions").stat().st_mode & 0o777 == 0o700
        finally:
            os.umask(previous)


if __name__ == "__main__":
    test_values_and_path_secrets()
    test_unsupported_files_are_ignored()
    test_symlink_is_rejected()
    test_bootstrap_executes_pi()
    test_root_is_rejected_before_secrets_or_exec()
    test_private_file_creation()
    print("bootstrap checks passed")
