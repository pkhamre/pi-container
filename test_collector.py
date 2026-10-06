#!/usr/bin/env python3
"""Exercise collector functions with temporary files and deterministic ldd output."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent
SOURCE = (REPO / "scripts/collect-runtime-deps.sh").read_text()
# Load the production functions without collecting the host's runtime tree.
FUNCTIONS, marker, _ = SOURCE.partition('for exe in "$@"; do\n')
assert marker, "collector executable loop not found"


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "rootfs"
        self.log = self.base / "copies"
        self.lib = self.base / "shared.so"
        self.lib.write_text("shared library\n")

    def file(self, name):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n")
        return path

    def run_collector(self, body, **variables):
        script = FUNCTIONS + '''
cp() {
  printf '%s\\n' "$2" >> "$COPY_LOG"
  command cp "$@"
}
ldd() { printf 'libfixture.so => %s (0x123)\\n' "$LIB"; }
''' + body
        return subprocess.run(
            ["bash", "-c", script, "collector-test", str(self.root), "unused"],
            env={**os.environ, "COPY_LOG": str(self.log), "LIB": str(self.lib),
                 **{key: str(value) for key, value in variables.items()}},
            capture_output=True, text=True,
        )

    def successful(self, body, **variables):
        result = self.run_collector(body, **variables)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.log.read_text().splitlines()

    def copied(self, path):
        return self.root / str(path).lstrip("/")

    def test_shared_libraries_and_duplicate_requests_copy_once(self):
        first, second = self.file("first"), self.file("second")
        copies = self.successful('process "$FIRST"\nprocess "$SECOND"\nprocess "$FIRST"\n',
                                 FIRST=first, SECOND=second)
        for path in (first, second, self.lib):
            self.assertEqual(copies.count(str(path)), 1)
            self.assertEqual(self.copied(path).read_bytes(), path.read_bytes())

    def test_distinct_symlink_aliases_keep_one_target(self):
        target = self.file("target")
        aliases = [self.base / "alias-one", self.base / "alias-two"]
        for alias in aliases:
            alias.symlink_to(target)
        copies = self.successful('process "$FIRST"\nprocess "$SECOND"\n',
                                 FIRST=aliases[0], SECOND=aliases[1])
        self.assertEqual(copies.count(str(target)), 1)
        for alias in aliases:
            self.assertTrue(self.copied(alias).is_symlink())
            self.assertEqual(os.readlink(self.copied(alias)), str(target))
            self.assertEqual(copies.count(str(alias)), 1)

    def test_directory_coverage_still_collects_external_link_target(self):
        child = self.file("modules/npm/cli.js")
        external = self.file("external")
        link = child.parent / "external-link"
        link.symlink_to(external)
        modules = self.base / "modules"
        copies = self.successful('cp_with_parents "$MODULES"\ncp_with_parents "$CHILD"\n'
                                 'cp_with_parents "$LINK"\ncp_with_parents "$MODULES"\n',
                                 MODULES=modules, CHILD=child, LINK=link)
        self.assertEqual(copies, [str(modules), str(external)])
        self.assertTrue(self.copied(link).is_symlink())
        self.assertTrue(self.copied(external).is_file())
        self.assertEqual(self.copied(child).read_bytes(), child.read_bytes())

    def test_node_roots_and_cli_links_collected_once(self):
        cli = self.file("modules/npm/cli.js")
        modules = self.base / "modules"
        link = self.base / "npm"
        link.symlink_to(cli)
        copies = self.successful('NODE_PATHS=("$MODULES" "$CLI_LINK")\n'
                                 'collect_node\ncollect_node\ncp_with_parents "$CLI"\n',
                                 MODULES=modules, CLI_LINK=link, CLI=cli)
        self.assertEqual(copies, [str(modules), str(link)])
        self.assertTrue(self.copied(link).is_symlink())
        self.assertTrue(self.copied(cli).is_file())

    def test_default_node_paths_do_not_overlap(self):
        result = self.run_collector('printf "%s\\n" "${NODE_PATHS[@]}"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = result.stdout.splitlines()
        for parent in paths:
            for child in paths:
                if parent != child:
                    self.assertFalse(child.startswith(parent + "/"), (parent, child))

    def test_missing_executable_fails(self):
        result = subprocess.run(
            ["bash", str(REPO / "scripts/collect-runtime-deps.sh"),
             str(self.root), str(self.base / "does-not-exist")],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing executable", result.stderr)

    def test_dependency_errors_are_not_ignored(self):
        exe = self.file("executable")
        missing = self.base / "missing.so"
        result = self.run_collector('process "$EXE"\n', EXE=exe, LIB=missing)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing shared library", result.stderr)
        result = self.run_collector('ldd() { echo "resolver failed"; return 1; }\n'
                                    'process "$EXE"\n', EXE=exe)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to resolve shared libraries", result.stderr)


if __name__ == "__main__":
    unittest.main()
