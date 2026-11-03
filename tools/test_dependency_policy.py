"""Offline policy regression tests using harmless, synthetic package registries.

Run with Python 3.11+ and the project's supported npm and uv on PATH:
    python tools/test_dependency_policy.py
No public registry packages or application databases are used.
"""

import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import tomllib
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("age-policy-parent", "age-policy-child")
VERSIONS = ("1.0.0", "1.1.0")


def run(command, directory, *, input=None):
    env = os.environ.copy()
    # Do not inherit personal registry credentials or package-manager policies.
    for name in list(env):
        if name.lower().startswith(("npm_config_", "uv_")):
            del env[name]
    env.update(
        NPM_CONFIG_USERCONFIG=str(directory / "empty-user-npmrc"),
        NPM_CONFIG_GLOBALCONFIG=str(directory / "empty-global-npmrc"),
        NPM_CONFIG_CACHE=str(directory / "npm-cache"),
        UV_CACHE_DIR=str(directory / "uv-cache"),
        UV_PYTHON_DOWNLOADS="never",
    )
    result = subprocess.run(
        command,
        cwd=directory,
        env=env,
        input=input,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode:
        raise AssertionError(
            f"{command} exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
        )
    return result


class Registry:
    """Serve two packages, each with one mature and one one-day-old version."""

    def __enter__(self):
        routes = {}

        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                route = routes.get(self.path)
                if route is None:
                    self.send_error(404)
                    return
                content_type, body = route
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        now = datetime.now(timezone.utc)
        dates = {
            version: (now - timedelta(days=days)).isoformat().replace("+00:00", "Z")
            for version, days in zip(VERSIONS, (30, 1))
        }
        for name in NAMES:
            npm_versions = {}
            wheel_files = []
            for version in VERSIONS:
                package = {"name": name, "version": version}
                if name == NAMES[0]:
                    package["dependencies"] = {NAMES[1]: "^1.0.0"}
                # An install script that must never run under the project policy.
                package["scripts"] = {
                    "install": "node -e \"require('fs').writeFileSync('install-script-ran', 'bad')\""
                }
                archive = io.BytesIO()
                with tarfile.open(fileobj=archive, mode="w:gz") as tar:
                    body = json.dumps(package).encode()
                    info = tarfile.TarInfo("package/package.json")
                    info.size = len(body)
                    tar.addfile(info, io.BytesIO(body))
                body = archive.getvalue()
                archive_path = f"/{name}/-/{name}-{version}.tgz"
                routes[archive_path] = ("application/octet-stream", body)
                npm_versions[version] = {
                    **package,
                    "dist": {
                        "tarball": self.url + archive_path,
                        "shasum": hashlib.sha1(body).hexdigest(),
                    },
                }

                normalized = name.replace("-", "_")
                filename = f"{normalized}-{version}-py3-none-any.whl"
                dist_info = f"{normalized}-{version}.dist-info"
                metadata = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
                if name == NAMES[0]:
                    metadata += f"Requires-Dist: {NAMES[1]}>=1.0.0\n"
                wheel = io.BytesIO()
                with ZipFile(wheel, "w") as archive:
                    archive.writestr(f"{dist_info}/METADATA", metadata)
                    archive.writestr(
                        f"{dist_info}/WHEEL",
                        "Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
                    )
                    archive.writestr(f"{dist_info}/RECORD", "")
                body = wheel.getvalue()
                routes[f"/files/{filename}"] = ("application/octet-stream", body)
                wheel_files.append(
                    {
                        "filename": filename,
                        "url": f"{self.url}/files/{filename}",
                        "hashes": {"sha256": hashlib.sha256(body).hexdigest()},
                        "upload-time": dates[version],
                    }
                )
            routes[f"/{name}"] = (
                "application/json",
                json.dumps(
                    {
                        "name": name,
                        "dist-tags": {"latest": VERSIONS[-1]},
                        "versions": npm_versions,
                        "time": dates,
                    }
                ).encode(),
            )
            routes[f"/simple/{name}/"] = (
                "application/vnd.pypi.simple.v1+json",
                json.dumps(
                    {"meta": {"api-version": "1.0"}, "name": name, "files": wheel_files}
                ).encode(),
            )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()


class DependencyPolicyTests(unittest.TestCase):
    def test_policy_settings_and_reviewed_bootstrap_versions(self):
        npm = configparser.ConfigParser()
        npm.read_string("[npm]\n" + (ROOT / ".npmrc").read_text())
        self.assertEqual(npm.getint("npm", "min-release-age"), 7)
        self.assertTrue(npm.getboolean("npm", "engine-strict"))
        self.assertTrue(npm.getboolean("npm", "ignore-scripts"))
        package = json.loads((ROOT / "package.json").read_text())
        self.assertEqual(package["engines"]["npm"], ">=11.17.0")
        uv = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]
        self.assertEqual(uv["exclude-newer"], "7 days")
        version = uv["required-version"].removeprefix(">=")
        for filename in ("Dockerfile", ".github/workflows/django.yml"):
            pins = re.findall(r"\buv==([\d.]+)", (ROOT / filename).read_text())
            self.assertTrue(pins, filename)
            self.assertEqual(set(pins), {version}, filename)

    @unittest.skipUnless(shutil.which("npm"), "npm is required")
    def test_npm_cooldown_transitives_scripts_and_emergency_override(self):
        with tempfile.TemporaryDirectory() as temporary, Registry() as registry:
            directory = Path(temporary)
            shutil.copy(ROOT / ".npmrc", directory)
            package = {
                "name": "policy-test",
                "version": "1.0.0",
                "dependencies": {NAMES[0]: "^1.0.0"},
                "engines": json.loads((ROOT / "package.json").read_text())["engines"],
            }
            (directory / "package.json").write_text(json.dumps(package))
            registry_arg = f"--registry={registry.url}"
            run(["npm", "install", registry_arg, "--no-audit", "--no-fund"], directory)
            lock = json.loads((directory / "package-lock.json").read_text())
            for name in NAMES:
                self.assertEqual(
                    lock["packages"][f"node_modules/{name}"]["version"], "1.0.0"
                )
            self.assertFalse(list(directory.rglob("install-script-ran")))
            # A constraint requiring only a young release must fail closed.
            package["dependencies"][NAMES[0]] = "^1.1.0"
            (directory / "package.json").write_text(json.dumps(package))
            with self.assertRaisesRegex(AssertionError, "ETARGET"):
                run(
                    ["npm", "install", registry_arg, "--no-audit", "--no-fund"],
                    directory,
                )
            # Explicitly review/opt in to a young release for an emergency.
            run(
                [
                    "npm",
                    "update",
                    registry_arg,
                    f"--min-release-age-exclude={NAMES[0]}",
                    "--no-audit",
                    "--no-fund",
                ],
                directory,
            )
            lock = json.loads((directory / "package-lock.json").read_text())
            self.assertEqual(
                lock["packages"][f"node_modules/{NAMES[0]}"]["version"], "1.1.0"
            )
            self.assertEqual(
                lock["packages"][f"node_modules/{NAMES[1]}"]["version"], "1.0.0"
            )
            # A reviewed lockfile (including an emergency exception) is reproducible.
            before = (directory / "package-lock.json").read_bytes()
            run(["npm", "ci", registry_arg, "--no-audit", "--no-fund"], directory)
            self.assertEqual((directory / "package-lock.json").read_bytes(), before)
            self.assertFalse(list(directory.rglob("install-script-ran")))

    @unittest.skipUnless(shutil.which("npm"), "npm is required")
    def test_npm_rejects_unsupported_package_manager(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            shutil.copy(ROOT / ".npmrc", directory)
            (directory / "package.json").write_text(
                json.dumps({"name": "unsupported-client", "engines": {"npm": ">=999"}})
            )
            with self.assertRaisesRegex(AssertionError, "EBADENGINE"):
                run(
                    ["npm", "install", "--offline", "--no-audit", "--no-fund"],
                    directory,
                )

    @unittest.skipUnless(shutil.which("uv"), "uv is required")
    def test_uv_cooldown_transitives_locked_install_and_emergency_override(self):
        with tempfile.TemporaryDirectory() as temporary, Registry() as registry:
            directory = Path(temporary)
            uv = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]
            (directory / "pyproject.toml").write_text(
                '[project]\nname = "policy-test"\nversion = "1.0.0"\n'
                'requires-python = ">=3.11"\ndependencies = ["age-policy-parent>=1.0.0"]\n'
                f'[tool.uv]\nrequired-version = "{uv["required-version"]}"\n'
                f'exclude-newer = "{uv["exclude-newer"]}"\n'
                f'[[tool.uv.index]]\nurl = "{registry.url}/simple/"\ndefault = true\n'
            )
            run(["uv", "lock"], directory)
            lock = tomllib.loads((directory / "uv.lock").read_text())
            versions = {p["name"]: p["version"] for p in lock["package"]}
            for name in NAMES:
                self.assertEqual(versions[name], "1.0.0")
            before = (directory / "uv.lock").read_bytes()
            run(["uv", "sync", "--locked"], directory)
            self.assertEqual((directory / "uv.lock").read_bytes(), before)
            project = directory / "pyproject.toml"
            project.write_text(
                project.read_text().replace(
                    "age-policy-parent>=1.0.0", "age-policy-parent>=1.1.0"
                )
            )
            with self.assertRaisesRegex(AssertionError, "No solution found"):
                run(["uv", "lock"], directory)
            # Record a narrow, reviewable exception so CI and collaborators agree.
            project.write_text(
                project.read_text().replace(
                    "[tool.uv]\n",
                    f'[tool.uv]\nexclude-newer-package = {{ "{NAMES[0]}" = "0 days" }}\n',
                )
            )
            run(["uv", "lock", "--upgrade-package", NAMES[0]], directory)
            lock = tomllib.loads((directory / "uv.lock").read_text())
            versions = {p["name"]: p["version"] for p in lock["package"]}
            self.assertEqual(versions[NAMES[0]], "1.1.0")
            self.assertEqual(versions[NAMES[1]], "1.0.0")
            run(["uv", "sync", "--locked"], directory)

    @unittest.skipUnless(
        os.environ.get("VERIFY_DOCKER_CONTEXT") == "1" and shutil.which("docker"),
        "set VERIFY_DOCKER_CONTEXT=1 with Docker running to check the build allowlist",
    )
    def test_docker_context_allowlist(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            context = directory / "source"
            context.mkdir()
            shutil.copy(ROOT / ".dockerignore", context)
            included = [
                "manage.py",
                "README.md",
                "pyproject.toml",
                "uv.lock",
                "pub_trivia/settings.py",
                "quiz/fixtures/content.json",
                "templates/base.html",
                "static/app.js",
            ]
            excluded = [
                ".env",
                "gsheets_key.json",
                ".git/config",
                ".venv/bin/python",
                "node_modules/package.json",
                "e2e/tests/test.ts",
                "playwright-report/index.html",
                "db_initial_data.json",
                "pub_trivia/.env",
                "quiz/gsheets_key.json",
                "quiz/secret.key",
                "quiz/__pycache__/test.pyc",
                "static/node_modules/package.json",
            ]
            for name in included + excluded:
                path = context / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("harmless test fixture")
            output = directory / "output"
            run(
                [
                    "docker",
                    "build",
                    "--output",
                    f"type=local,dest={output}",
                    "-f",
                    "-",
                    str(context),
                ],
                directory,
                input="FROM scratch\nCOPY . /context/\n",
            )
            for name in included:
                self.assertTrue((output / "context" / name).exists(), name)
            for name in excluded:
                self.assertFalse((output / "context" / name).exists(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
