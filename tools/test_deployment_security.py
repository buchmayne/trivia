"""Offline deployment configuration checks; never connects to production.

Run: python tools/test_deployment_security.py
Compose validation needs the Docker CLI/Compose plugin, not a running daemon.
"""

import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DeploymentWorkflowTests(unittest.TestCase):
    def test_deploy_uses_reviewed_action_and_helper_with_read_only_permissions(self):
        workflow = (ROOT / ".github/workflows/django.yml").read_text()
        deploy = workflow.split("\n  deploy:", 1)[1]
        self.assertIn("needs: [test, dependency-policy]", deploy)
        self.assertRegex(deploy, r"permissions:\s+contents: read")
        pins = re.findall(r"uses: appleboy/ssh-action@([^\s]+)", deploy)
        self.assertEqual(pins, ["0ff4204d59e8e51228ff73bce53f80d53301dee2"])
        self.assertRegex(deploy, r"version: '1\.8\.2'")
        self.assertIn("github.ref == 'refs/heads/main'", deploy)
        self.assertIn("github.event_name == 'push'", deploy)

    @unittest.skipUnless(shutil.which("bash"), "bash is required")
    def test_actual_secret_file_commands_restrict_new_and_existing_files(self):
        workflow = (ROOT / ".github/workflows/django.yml").read_text()
        start = workflow.index("          umask 077\n")
        end = workflow.index("          # Build the new images", start)
        # Run only the actual .env-writing portion, never the deploy/prune script.
        script = textwrap.dedent(workflow[start:end])
        script = re.sub(r"\$\{\{ secrets\.[A-Z0-9_]+ \}\}", "test-value", script)
        self.assertNotIn("${{", script)
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                env_file = directory / ".env"
                if existing:
                    env_file.write_text("old-value\n")
                    env_file.chmod(0o644)
                result = subprocess.run(
                    ["bash", "-eu", "-c", "umask 022\n" + script],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)
                self.assertIn("DEBUG=False\n", env_file.read_text())
                self.assertIn("DB_PASSWORD=test-value\n", env_file.read_text())
                # chmod must precede the first secret write, not just fix it later.
                self.assertLess(
                    script.index("chmod 600 .env"), script.index("DB_NAME=")
                )


@unittest.skipUnless(shutil.which("docker"), "Docker CLI/Compose is required")
class ComposeBoundaryTests(unittest.TestCase):
    def test_normalized_compose_keeps_database_local_and_internal_routes_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy(ROOT / "docker-compose.yml", directory)
            # Never read the repository's real .env or print interpolated secrets.
            (directory / ".env").write_text(
                "DB_NAME=test_db\nDB_USER=test_user\nDB_PASSWORD=test-password\n"
                "BACKUP_S3_BUCKET=test-bucket\nBACKUP_S3_REGION=us-west-2\n"
                "BACKUP_AWS_ACCESS_KEY_ID=test-key\n"
                "BACKUP_AWS_SECRET_ACCESS_KEY=test-secret\n"
            )
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "--project-directory",
                    str(directory),
                    "--file",
                    str(directory / "docker-compose.yml"),
                    "config",
                    "--format",
                    "json",
                ],
                env={"PATH": os.environ["PATH"], "HOME": os.environ["HOME"]},
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            services = json.loads(result.stdout)["services"]
            ports = services["db"]["ports"]
            self.assertEqual(len(ports), 1)
            self.assertEqual(ports[0]["host_ip"], "127.0.0.1")
            self.assertEqual(str(ports[0]["published"]), "5433")
            self.assertEqual(ports[0]["target"], 5432)
            self.assertEqual(services["web"]["environment"]["DB_HOST"], "db")
            self.assertEqual(services["web"]["environment"]["DB_PORT"], "5432")
            self.assertEqual(
                services["db-backup"]["environment"]["POSTGRES_HOST"], "db"
            )
            self.assertTrue(
                any(
                    volume["source"] == "postgres_data"
                    and volume["target"] == "/var/lib/postgresql/data"
                    for volume in services["db"]["volumes"]
                )
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
