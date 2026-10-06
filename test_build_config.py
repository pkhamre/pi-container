#!/usr/bin/env python3
"""Guard build defaults and cache-sensitive argument placement without Docker."""
from pathlib import Path
import re
import subprocess
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
