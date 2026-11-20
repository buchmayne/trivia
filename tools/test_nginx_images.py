"""Opt-in integration test of the real patched proxy and internal NGINX images.

Build first: docker compose build nginx-proxy && docker compose pull nginx
Run: VERIFY_NGINX_IMAGES=1 python tools/test_nginx_images.py
Uses isolated containers, a self-signed certificate, and no application secrets.
The Docker socket is mounted read-only for nginx-proxy's normal discovery.
"""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROXY_IMAGE = "trivia-nginx-proxy:nginx-1.31.9"
NGINX_IMAGE = (
    "nginx:1.31.9-alpine@sha256:"
    "fb4658584bd9a916ffb6f6e365f97c25cfdb2923801f551ea08356e695f14ff7"
)


def run(*command):
    return subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=60
    ).stdout.strip()


@unittest.skipUnless(
    os.environ.get("VERIFY_NGINX_IMAGES") == "1", "set VERIFY_NGINX_IMAGES=1"
)
class NginxImagesTests(unittest.TestCase):
    def test_https_http2_discovery_and_static_files(self):
        prefix = "nginx-security-test-" + uuid.uuid4().hex[:10]
        names = [prefix + suffix for suffix in ("-web", "-internal", "-proxy")]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            certs = directory / "certs"
            certs.mkdir()
            static = directory / "static"
            static.mkdir()
            (static / "probe.css").write_text("body { color: green; }\n")
            backend_conf = directory / "backend.conf"
            backend_conf.write_text(
                "server { listen 8000; location / { "
                "return 200 'patched-proxy-ok'; } }\n"
            )
            run(
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=nginx-security.test",
                "-addext",
                "subjectAltName=DNS:nginx-security.test",
                "-keyout",
                str(certs / "nginx-security.test.key"),
                "-out",
                str(certs / "nginx-security.test.crt"),
            )
            run("docker", "network", "create", prefix)
            try:
                run(
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    names[0],
                    "--network",
                    prefix,
                    "--network-alias",
                    "web",
                    "-v",
                    f"{backend_conf}:/etc/nginx/conf.d/default.conf:ro",
                    NGINX_IMAGE,
                )
                run(
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    names[1],
                    "--network",
                    prefix,
                    "-e",
                    "VIRTUAL_HOST=nginx-security.test",
                    "-e",
                    "VIRTUAL_PORT=80",
                    "-e",
                    "HTTPS_METHOD=noredirect",
                    "-v",
                    f"{ROOT / 'nginx.conf'}:/etc/nginx/conf.d/default.conf:ro",
                    "-v",
                    f"{static}:/app/staticfiles:ro",
                    NGINX_IMAGE,
                )
                run(
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    names[2],
                    "--network",
                    prefix,
                    "-p",
                    "127.0.0.1::443",
                    "-v",
                    "/var/run/docker.sock:/tmp/docker.sock:ro",
                    "-v",
                    f"{certs}:/etc/nginx/certs:ro",
                    PROXY_IMAGE,
                )
                for name in names[1:]:
                    # nginx -v writes to stderr; validate the actual running binary.
                    version = subprocess.run(
                        ["docker", "exec", name, "nginx", "-v"],
                        check=True,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(
                        version.stderr.strip(), "nginx version: nginx/1.31.9"
                    )
                    run("docker", "exec", name, "nginx", "-t")
                port = json.loads(
                    run(
                        "docker",
                        "inspect",
                        names[2],
                        "--format",
                        "{{json .NetworkSettings.Ports}}",
                    )
                )["443/tcp"][0]["HostPort"]
                curl = [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--fail",
                    "--http2",
                    "--noproxy",
                    "*",
                    "--max-time",
                    "5",
                    "--cacert",
                    str(certs / "nginx-security.test.crt"),
                    "--resolve",
                    f"nginx-security.test:{port}:127.0.0.1",
                ]
                response = None
                for attempt in range(20):
                    try:
                        response = run(
                            *curl,
                            "--write-out",
                            "\n%{http_version}",
                            f"https://nginx-security.test:{port}/",
                        )
                        break
                    except subprocess.CalledProcessError:
                        if attempt == 19:
                            raise
                        time.sleep(1)
                self.assertIsNotNone(response)
                self.assertEqual(response, "patched-proxy-ok\n2")
                response = run(
                    *curl,
                    "--include",
                    f"https://nginx-security.test:{port}/static/probe.css",
                )
                self.assertIn("content-type: text/css", response.lower())
                self.assertIn("body { color: green; }", response)
            finally:
                for name in reversed(names):
                    subprocess.run(
                        ["docker", "rm", "-f", name], capture_output=True, timeout=30
                    )
                run("docker", "network", "rm", prefix)


if __name__ == "__main__":
    unittest.main(verbosity=2)
