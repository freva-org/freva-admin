# Institution-managed reverse proxy

Freva does not install or configure a reverse proxy, an ingress controller, or
TLS certificates. The deployment exposes the Django web application and REST
API so the institution can connect them to its normal HTTP infrastructure.

For an all-in-one Quadlet host, the relevant defaults are:

| Backend | Address | Purpose |
| --- | --- | --- |
| Django | `127.0.0.1:8000` | Web application |
| REST API | `127.0.0.1:7777` | Freva APIs |
| Static files | `/var/lib/freva/<project>/web/static` | Collected web assets |
| Preview files | `/var/lib/freva/<project>/work/share/preview` | Generated previews |

Set `web_bind_address` when the reverse proxy runs on another host. Restrict
the published port with the host firewall and do not expose Django directly to
an untrusted network.

## Minimal nginx example

This example terminates TLS and covers the routes expected by the current web
application. Certificate enrollment, renewal, cipher policy, access logging,
rate limits, and monitoring remain the administrator's responsibility.
Replace the example host, certificate paths, and `freva` path segment with the
institution's values.

```nginx
upstream freva_web {
    server 127.0.0.1:8000;
}

upstream freva_rest {
    server 127.0.0.1:7777;
}

server {
    listen 443 ssl;
    server_name freva.example.org;

    ssl_certificate /etc/pki/tls/certs/freva.example.org.crt;
    ssl_certificate_key /etc/pki/tls/private/freva.example.org.key;

    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-Port 443;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;

    location /static/preview/ {
        alias /var/lib/freva/freva/work/share/preview/;
    }

    location /static/ {
        alias /var/lib/freva/freva/web/static/;
    }

    # Public Zarr sharing may be read by browsers on other origins.
    location ^~ /api/freva-nextgen/data-portal/share/ {
        add_header Access-Control-Allow-Origin "*" always;
        add_header Access-Control-Allow-Methods "GET, HEAD, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Origin,Content-Type,Range" always;
        add_header Access-Control-Expose-Headers \
            "Accept-Ranges,Content-Length,Content-Range,Content-Type,ETag" always;

        if ($request_method = OPTIONS) {
            return 204;
        }

        proxy_pass http://freva_rest;
    }

    location /api/freva-nextgen/ {
        proxy_pass http://freva_rest;
    }

    # Compatibility routes for older web clients.
    location /api/databrowser/metadata_search/ {
        proxy_pass http://freva_rest/api/freva-nextgen/databrowser/metadata-search/;
    }

    location /api/databrowser/data_search/ {
        proxy_pass http://freva_rest/api/freva-nextgen/databrowser/data-search/;
    }

    location /api/freva-data-portal/ {
        proxy_pass http://freva_rest/api/freva-nextgen/data-portal/;
    }

    location /api/auth/ {
        proxy_pass http://freva_rest/api/freva-nextgen/auth/;
    }

    location / {
        proxy_pass http://freva_web;
    }
}
```

If the optional chatbot is enabled, add this location to the server block and
set the headers it needs:

```nginx
location /api/chatbot/ {
    proxy_pass http://127.0.0.1:9000/api/chatbot/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto https;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Freva-Project freva;
    proxy_set_header X-Freva-Rest-URL https://freva.example.org;
    proxy_set_header X-Freva-Config-Path \
        /var/lib/freva/freva/core/freva/evaluation_system.conf;
}
```

The authenticated API should normally stay same-origin. If an institution
allows other browser origins, it must define an explicit CORS policy rather
than copying the wildcard policy from the public share endpoint.

## Certificates and SELinux

No certificate or private-key examples are stored in this repository. Use the
institution's certificate service, ACME client, Kubernetes Secret, or other
established mechanism. Do not pass private TLS keys through the public Ansible
roles.

The Quadlet roles label Freva state as `container_file_t`. A host nginx process
running as `httpd_t` may need an institution-owned SELinux policy allowing
read-only access to the static and preview trees. An alternative is to publish
those files into a separate `httpd_sys_content_t` tree.

For Kubernetes, the Helm chart exposes Services only. The site repository must
provide its Ingress or Gateway resources and a static-file service with access
to the web PVC when the ingress controller cannot serve that volume directly.
