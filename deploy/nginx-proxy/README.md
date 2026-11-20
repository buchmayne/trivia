# NGINX security patch (2026-11-20)

## Decision and scope

CVE-2026-123007 and CVE-2026-123633 affect the public HTTP/2 proxy. The
running site was confirmed to negotiate HTTP/2 and both NGINX containers
reported 1.31.3. Upstream lists 1.31.9 mainline and 1.30.7 stable as fixed:
<https://nginx.org/en/security_advisories.html>.

The nginx-proxy 1.11.6 release and the vendor's current Dockerfiles still
use vulnerable NGINX. `deploy/nginx-proxy/Dockerfile` therefore preserves
1.11.6's static docker-gen/forego executables, template, startup scripts,
and proxy configuration on the digest-pinned official NGINX 1.31.9 image.
It deliberately does not copy the old NGINX binary, libraries, or modules.
The internal NGINX also uses a digest-pinned official 1.31.9 Alpine image.
HTTP/2 stays enabled because the actual runtime is patched.

This is a narrow runtime patch: application code, PostgreSQL, certificate
volumes, and backup configuration do not change. No Java/OpenJDK-specific
change is indicated by this repository's deployment configuration.

The image digests were checked against Docker Hub. The urgent security
patch is intentionally adopted without waiting seven days; the registry
cooldown for Python/npm does not govern Docker images.

## Verification

```sh
python tools/test_deployment_security.py
docker compose build nginx-proxy
docker compose pull nginx
VERIFY_NGINX_IMAGES=1 python tools/test_nginx_images.py
git diff --check
```

The opt-in integration test uses the actual patched images and checked-in
internal NGINX configuration on an isolated network. It checks both running
binaries, valid configuration, docker-gen backend discovery, HTTPS with a
test certificate, HTTP/2 negotiation, and static-file content and MIME type.
It does not load `.env`, use production credentials, or access production.
It requires Docker, OpenSSL, and curl with HTTP/2 support. Its nginx-proxy
container mounts the local Docker socket for ordinary discovery; run only
on a trusted development/test Docker host. Created containers/network are
removed afterward.

## Production rollout

Build/pull before stopping any live service. Preflight the candidate images
with `nginx -t` against the live mounts (read-only) on the Compose network.
Retain the previous image IDs/tags for emergency rollback. Replace only the
`nginx-proxy` and `nginx` services, not the database or application. Legacy
Compose 1.29 may require explicitly removing these two containers before
`up --no-deps` when paired with newer Docker engines. Do not remove volumes.
After replacement, recreate the ACME companion so its `volumes_from` binding
and discovery target refer to the new proxy container; its certificate and
account volumes are preserved.

Verify both running binaries are 1.31.9, both configurations pass `nginx -t`,
and the running image IDs match the built/pulled images. Check both public
hostnames over HTTP/2 and HTTP/1.1, HTTP-to-HTTPS redirects, and a real static
asset. Check application/database container IDs and start times are unchanged.
The normal workflow now explicitly pulls the pinned internal image before
building and taking down services.

### Direct deployment before the human commits

No assistant-created commit or push is required for an emergency direct
rollout. Copy the proxy Dockerfile to its matching production path and use a
small **untracked** `docker-compose.override.yml` selecting the same patched
proxy build/image and pinned internal image as the repository's Compose file.
Confirm no override already exists before creating it; never overwrite an
operator's existing configuration. Compose automatically applies this file.

This temporary override prevents the workflow's `git reset --hard origin/main`
from undoing the security fix before the human merges it. Keep the Dockerfile
at its production path too. The production repository will show untracked
patch files until the human commits and merges the source changes. Once the
patched tracked Compose file and Dockerfile are deployed from main, compare
resolved configurations and remove the temporary override. Do not run
`git clean` against the emergency patch files before that handoff.

Rollback must restore the previous service images and configuration without
removing volumes. Old NGINX is vulnerable: disable HTTP/2 and verify the
generated configuration and public ALPN negotiation if rollback is necessary.

## Completed rollout (2026-11-20, approximately 21:04 UTC)

- Built and preflighted both candidate images on the Droplet before cutover.
- Replaced both NGINX containers and recreated the existing ACME companion.
  Both running binaries report 1.31.9; image IDs match the intended images.
- Both public hostnames return HTTP 200 using HTTP/2 and HTTP/1.1, with valid
  TLS verification. HTTP redirects to HTTPS and real CSS assets return 200.
- ACME companion discovery references the new proxy; existing certificates
  remain valid and the helper reports the next renewal is not yet due.
- Application, database, and database-backup container IDs and start times
  are unchanged. PostgreSQL remains healthy.
- Local checks passed: four deployment checks, the real-image integration
  test, two audit-entry-point checks, lockfile validation, and all 468 Django
  tests against a disposable PostgreSQL 14 container (not production data).
- The production override is `/root/opt/trivia/docker-compose.override.yml`;
  the matching Dockerfile is `/root/opt/trivia/deploy/nginx-proxy/Dockerfile`.
  Previous image tags are `trivia-nginx-proxy:rollback-20261120` and
  `trivia-nginx-internal:rollback-20261120`. Pre-rollout configuration and
  image/container identity records are under `/root/nginx-security-20261120`.
- No code was committed or pushed. Merge this source patch before removing
  the temporary production override. It intentionally survives ordinary
  deployment resets in the meantime.

Full browser UI verification was not run because Chrome DevTools MCP was
unavailable. The checks above exercise the actual containers and HTTPS
endpoints, not browser-rendered interactions. The Droplet has about 800 MB
free disk space after the rollout; more disk headroom is recommended.
