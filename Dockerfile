FROM debian:stable-backports

ARG VERSION
LABEL org.opencontainers.image.authors="DRKZ-CLINT"
LABEL org.opencontainers.image.source="https://github.com/freva-org/freva-deployment.git"
LABEL org.opencontainers.image.version="$VERSION"

ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV PIP_ROOT_USER_ACTION=ignore

# Install required packages including locales
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-cryptography \
    python3-dev \
    python3-pip \
    python3-bcrypt \
    openssh-client \
    sshpass \
    git \
    binutils \
    python3-mysqldb \
    python3-yaml \
    python3-toml \
    python3-tomlkit \
    python3-requests \
    python3-rich \
    python3-paramiko \
    python3-pymysql \
    python3-full \
    ansible \
    python3-mock \
    mysql-common && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for locale
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV LANGUAGE=C.UTF-8

# Set up work directories
RUN mkdir -p /opt/freva-deployment /tmp/deployment /src

WORKDIR /tmp/deployment

# Copy all files into the container
COPY . .

# Install Python dependencies
RUN python3 src/freva_deployment/__init__.py && \
    python3 -m pip install --break-system-packages pyinstaller appdirs rich-argparse namegenerator npyscreen && \
    python3 -m pip install --break-system-packages --no-deps . &&\
    rm -rf /root/.cache/pip && \
    rm -rf /root/build-deps && \
    rm -rf /tmp/deployment

WORKDIR /opt/freva-deployment

# Define volumes
VOLUME /opt/freva-deployment
VOLUME /src

# Define the default command
CMD ["/usr/local/bin/deploy-freva"]
