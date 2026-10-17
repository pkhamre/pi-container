#!/usr/bin/env python3
"""Guard build defaults and cache-sensitive argument placement without Docker."""
from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent
DOCKERFILE = (REPO / "Dockerfile").read_text()
MAKEFILE = (REPO / "Makefile").read_text()


class BuildConfigTests(unittest.TestCase):
    def test_package_defaults_agree(self):
        for name in ("NODE_MAJOR", "NPM_VERSION", "PI_VERSION"):
            docker = re.search(rf"^ARG {name}=(.+)$", DOCKERFILE, re.MULTILINE)
            make = re.search(rf"^{name} \?= (.+)$", MAKEFILE, re.MULTILINE)
            self.assertIsNotNone(docker)
            self.assertIsNotNone(make)
            self.assertEqual(docker[1], make[1], name)

    def test_pi_version_references_agree(self):
        version = re.search(r"^ARG PI_VERSION=(.+)$", DOCKERFILE, re.MULTILINE)[1]
        smoke = (REPO / "test_smoke.sh").read_text()
        self.assertIn(f'expected_version="${{PI_VERSION:-{version}}}"', smoke)
        readme = (REPO / "README.md").read_text()
        self.assertIn(f"exact published Pi version `{version}`", readme)
        examples = re.findall(r"PI_VERSION=([\d.]+)", readme)
        self.assertTrue(examples)
        self.assertTrue(all(example == version for example in examples))

    def test_versions_do_not_invalidate_os_install(self):
        builder = DOCKERFILE.split("FROM builder-tools AS collector")[0]
        os_install = builder.index("apt-get install")
        node_install = builder.index("mkdir -p /etc/apt/keyrings")
        npm_install = builder.index("npm install")
        self.assertLess(os_install, builder.index("ARG NODE_MAJOR="))
        self.assertLess(builder.index("ARG NODE_MAJOR="), node_install)
        for name in ("NPM_VERSION", "PI_VERSION"):
            self.assertLess(node_install, builder.index(f"ARG {name}="))
            self.assertLess(builder.index(f"ARG {name}="), npm_install)
        self.assertNotIn("ARG USER_UID", builder)
        self.assertNotIn("ARG USER_GID", builder)

    def run_latest_build(self, response, curl_status=0, version_override=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Makefile").write_text(MAKEFILE)
            curl = root / "curl"
            curl.write_text(
                '#!/bin/sh\nprintf "%s" "$REGISTRY_RESPONSE"\nexit "$CURL_STATUS"\n'
            )
            engine = root / "engine"
            engine.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$BUILD_LOG"\n')
            curl.chmod(0o755)
            engine.chmod(0o755)
            log = root / "build.log"
            command = ["make", "build-latest", f"ENGINE={engine}"]
            if version_override is not None:
                command.append(f"PI_VERSION={version_override}")
            result = subprocess.run(
                command,
                cwd=root,
                env={
                    **os.environ,
                    "PATH": f"{root}:{os.environ['PATH']}",
                    "REGISTRY_RESPONSE": response,
                    "CURL_STATUS": str(curl_status),
                    "BUILD_LOG": str(log),
                    "MAKEFLAGS": "",
                    "MFLAGS": "",
                    "MAKEOVERRIDES": "",
                },
                capture_output=True,
                text=True,
            )
            arguments = log.read_text().splitlines() if log.exists() else None
            return result, arguments

    def test_build_latest_uses_registry_version_instead_of_pin(self):
        latest = "999.0.0"
        for override in (None, "0.0.1"):
            with self.subTest(version_override=override):
                result, arguments = self.run_latest_build(
                    json.dumps({"version": latest}), version_override=override
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(arguments[0], "build")
                versions = [arg for arg in arguments if arg.startswith("PI_VERSION=")]
                self.assertEqual(versions, [f"PI_VERSION={latest}"])
                self.assertEqual(arguments[-3:], ["-t", "pi-container:latest", "."])

    def test_build_latest_does_not_build_when_lookup_fails(self):
        for response, status in (
            ("", 22),
            ("not json", 0),
            ("{}", 0),
            ('{"version": ""}', 0),
        ):
            with self.subTest(response=response, curl_status=status):
                result, arguments = self.run_latest_build(response, status)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(arguments, "lookup failure must not build the pinned version")

    def test_helm_checksums_are_pinned_before_extraction(self):
        version = re.search(r"^ARG HELM_VERSION=(.+)$", DOCKERFILE, re.MULTILINE)[1]
        pins = re.findall(
            r"(v[\d.]+)/(amd64|arm64)\) helm_arch=\w+; helm_sha256=([a-f0-9]{64});;",
            DOCKERFILE,
        )
        self.assertEqual({(v, arch) for v, arch, _ in pins},
                         {(version, "amd64"), (version, "arm64")})
        helm = DOCKERFILE.split("ARG HELM_VERSION=")[1].split("RUN node --version")[0]
        verification = 'printf \'%s  %s\\n\' "$helm_sha256" /tmp/helm.tar.gz | sha256sum -c - &&'
        self.assertIn(verification, helm)
        self.assertLess(helm.index(verification), helm.index("tar -xzf"))
        self.assertIn("add a verified checksum first", helm)

    def test_build_context_is_allowlisted(self):
        patterns = [line for line in (REPO / ".dockerignore").read_text().splitlines()
                    if line and not line.startswith("#")]
        self.assertEqual(patterns, ["**", "!Dockerfile", "!bootstrap.py", "!scripts/", "scripts/**",
                                    "!scripts/collect-runtime-deps.sh", "!custom-ca.crt"])

    def test_secret_mounts_and_loading_are_removed(self):
        for name in ("Dockerfile", "Makefile", "bootstrap.py", "bin/pi-container"):
            source = (REPO / name).read_text()
            self.assertNotIn("/run/secrets", source, name)
            self.assertNotIn("load_secrets", source, name)
        launcher = (REPO / "bin/pi-container").read_text()
        self.assertNotIn("--add-host", launcher)
        self.assertNotIn('"$STATE_DIR/secrets"', launcher)

    def test_build_uid_guard(self):
        guard = re.search(r'^RUN (test "\$\{USER_UID\}" -gt 0 .*});', DOCKERFILE, re.MULTILINE)
        self.assertIsNotNone(guard, "non-root UID build guard missing")
        for uid in ("0", "000", "-1", "invalid", "1000"):
            result = subprocess.run(["sh", "-c", guard[1]], env={"USER_UID": uid}, capture_output=True, text=True)
            self.assertEqual(result.returncode == 0, uid == "1000", (uid, result.stderr))

    def test_ownership_does_not_invalidate_collection(self):
        collector = DOCKERFILE.split("FROM builder-tools AS collector")[1].split("FROM gcr.io/")[0]
        collection = collector.index("collect-runtime-deps.sh")
        merge = collector.index("for dir in bin sbin lib lib64")
        ownership = collector.index("chown -R")
        for name in ("USER_UID", "USER_GID"):
            argument = collector.index(f"ARG {name}=")
            self.assertLess(collection, argument)
            self.assertLess(merge, argument)
            self.assertLess(argument, ownership)


if __name__ == "__main__":
    unittest.main()
