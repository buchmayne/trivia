"""Offline tests of the Python audit entry point and locked export boundary.

Run: python tools/test_python_audit.py
The real advisory-service check is `make audit-python` (requires network).
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("make"), "make is required")
class AuditCommandTests(unittest.TestCase):
    def test_exports_all_groups_audits_and_cleans_up_on_success_or_failure(self):
        # Stub only the external package manager, not the Makefile under test.
        # Real pip-audit success/vulnerability/service-error checks are recorded
        # separately in docs/python-security/verification.md.
        for export_exit, audit_exit in ((0, 0), (17, 0), (0, 1), (0, 23)):
            with self.subTest(export_exit=export_exit, audit_exit=audit_exit):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    executable = directory / "uv"
                    executable.write_text(
                        f"#!{sys.executable}\n"
                        "import json, os, pathlib, sys\n"
                        "args = sys.argv[1:]\n"
                        "with open(os.environ['AUDIT_LOG'], 'a') as log:\n"
                        "    log.write(json.dumps(args) + '\\n')\n"
                        "if args[0] == 'export':\n"
                        "    output = pathlib.Path(args[args.index('--output-file') + 1])\n"
                        "    output.write_text('example==1.0.0 --hash=sha256:abc\\n')\n"
                        "    sys.exit(int(os.environ['EXPORT_EXIT']))\n"
                        "sys.exit(int(os.environ['AUDIT_EXIT']))\n"
                    )
                    executable.chmod(0o755)
                    log = directory / "commands.jsonl"
                    result = subprocess.run(
                        ["make", "audit-python"],
                        cwd=ROOT,
                        env={
                            **os.environ,
                            "PATH": str(directory) + os.pathsep + os.environ["PATH"],
                            "TMPDIR": str(directory),
                            "AUDIT_LOG": str(log),
                            "EXPORT_EXIT": str(export_exit),
                            "AUDIT_EXIT": str(audit_exit),
                        },
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    self.assertEqual(
                        result.returncode == 0, not (export_exit or audit_exit)
                    )
                    commands = [
                        json.loads(line) for line in log.read_text().splitlines()
                    ]
                    export = commands[0]
                    self.assertEqual(
                        export[:5],
                        [
                            "export",
                            "--locked",
                            "--all-groups",
                            "--no-emit-project",
                            "--output-file",
                        ],
                    )
                    requirements = export[5]
                    self.assertFalse(
                        Path(requirements).exists(), "temporary export leaked"
                    )
                    if export_exit:
                        self.assertEqual(
                            len(commands), 1, "audited an unsuccessful export"
                        )
                    else:
                        self.assertEqual(
                            commands[1],
                            [
                                "run",
                                "--locked",
                                "--group",
                                "security",
                                "python",
                                "-m",
                                "pip_audit",
                                "--requirement",
                                requirements,
                                "--require-hashes",
                                "--disable-pip",
                                "--strict",
                            ],
                        )


@unittest.skipUnless(shutil.which("uv"), "uv is required")
class AuditExportTests(unittest.TestCase):
    def test_all_groups_are_exported_but_security_tools_are_not_production_dependencies(
        self,
    ):
        before = (ROOT / "uv.lock").read_bytes()
        lock = tomllib.loads(before.decode())

        def export(*groups):
            result = subprocess.run(
                ["uv", "export", "--offline", "--locked", "--no-emit-project", *groups],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--hash=sha256:", result.stdout)
            return set(re.findall(r"^([a-z0-9-]+)==([^\s;\\]+)", result.stdout, re.M))

        all_groups = export("--all-groups")
        expected = {
            (p["name"], p["version"])
            for p in lock["package"]
            if "registry" in p["source"]
        }
        self.assertEqual(all_groups, expected)
        self.assertNotIn(("trivia", "0.1.0"), all_groups)
        production = {name for name, _ in export("--no-dev")}
        for tooling in ("pip-audit", "cyclonedx-python-lib", "black"):
            self.assertNotIn(tooling, production)
        self.assertIn("django", production)
        self.assertIn("pillow", production)
        self.assertEqual((ROOT / "uv.lock").read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
