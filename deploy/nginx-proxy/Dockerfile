# Keep the existing nginx-proxy tooling/template while replacing its vulnerable
# NGINX runtime. Upstream nginx-proxy 1.11.6 still bundles NGINX 1.31.3.
FROM nginxproxy/nginx-proxy:1.11.6@sha256:dd78565eca9742624655bb743723e0aeeab552153c4eea01095e4266c59150d5 AS proxy

# CVE-2026-123007 / CVE-2026-123633: fixed official runtime, pinned by digest.
FROM nginx:1.31.9@sha256:84f7876d21d154885f99554d7ae325d8c2213f9169726ea7ab60642f2573a787

ENV NGINX_PROXY_VERSION=1.11.6-nginx-1.31.9 \
    DOCKER_GEN_VERSION=unknown \
    DOCKER_HOST=unix:///tmp/docker.sock

# These two Go executables are static. Do not copy the old NGINX binary,
# libraries, or modules into the patched runtime.
COPY --from=proxy /usr/local/bin/forego /usr/local/bin/forego
COPY --from=proxy /usr/local/bin/docker-gen /usr/local/bin/docker-gen
COPY --from=proxy /app/ /app/
COPY --from=proxy /etc/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=proxy /etc/nginx/network_internal.conf /etc/nginx/network_internal.conf

RUN mkdir -p /etc/nginx/toplevel.conf.d /etc/nginx/dhparam \
        /etc/nginx/certs /usr/share/nginx/html/errors \
    && test "$(nginx -v 2>&1)" = "nginx version: nginx/1.31.9"

WORKDIR /app
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["forego", "start", "-r"]
