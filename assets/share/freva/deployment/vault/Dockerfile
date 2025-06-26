FROM docker.io/mambaorg/micromamba:latest AS vault-builder
ARG VERSION
USER root
ENV PATH=/opt/conda/bin:$PATH

RUN set -eux && \
    micromamba install -q -y -c conda-forge --override-channels go curl jq\
    && micromamba clean -a -y

# Set working directory
WORKDIR /build

# Fetch latest Vault source code
RUN curl -sSL $(curl -s https://api.github.com/repos/hashicorp/vault/releases/latest | jq -r '.tarball_url') | tar xz --strip-components=1

# Build Vault
RUN set -eux \
    && mkdir -p /vault-bin \
    && CGO_ENABLED=0 GO111MODULE=on go build \
    -buildmode=pie \
    -trimpath \
    -modcacherw \
    -o /vault-bin/vault \
    -ldflags="-s -w"


FROM docker.io/mambaorg/micromamba
ARG VERSION
USER root
LABEL org.opencontainers.image.authors="DRKZ-CLINT"
LABEL org.opencontainers.image.source="https://github.com/freva-org/freva-deployment.git"
LABEL org.opencontainers.image.version="$VERSION"

ENV VAULT_ADDR='http://127.0.0.1:8200'

WORKDIR /opt/vault

COPY runserver.py /bin/runserver.py
COPY --from=vault-builder /vault-bin/vault /bin/vault
COPY add-vault-secret /bin/add-vault-secret
COPY vault-server-tls.hcl /opt/vault/
COPY policy-file.hcl /opt/vault/

RUN set -eux \
 && chmod +x /bin/runserver.py /bin/add-vault-secret \
 && mkdir -p /vault/file \
 && micromamba install -y -c conda-forge --override-channels fastapi pyopenssl uvicorn requests hvac \
 && micromamba clean -a -y \
 && chmod -R 1777 /vault && ln -s /opt/bin/python /bin/python

EXPOSE 5002
CMD python3 /bin/runserver.py && \
    uvicorn --workers 2 --app-dir /bin runserver:app \
    --host 0.0.0.0 --port 5002
