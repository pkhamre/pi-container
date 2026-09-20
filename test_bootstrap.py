#!/usr/bin/env python3
import tempfile
from pathlib import Path

import bootstrap


def test_values_and_path_secrets() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "anthropic_api_key").write_text("secret\n", encoding="utf-8")
        (root / "google_application_credentials").write_text("{}", encoding="utf-8")
        env = {}
        bootstrap.load_secrets(root, env)
        assert env["ANTHROPIC_API_KEY"] == "secret"
        assert env["GOOGLE_APPLICATION_CREDENTIALS"] == str(root / "google_application_credentials")


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
        bootstrap.bootstrap(["--version"], execvp=lambda program, args: events.append((program, args)))
    finally:
        bootstrap.load_secrets = original
    assert events == ["secrets", ("pi", ["pi", "--version"])]


if __name__ == "__main__":
    test_values_and_path_secrets()
    test_unsupported_files_are_ignored()
    test_symlink_is_rejected()
    test_bootstrap_executes_pi()
    print("bootstrap checks passed")
