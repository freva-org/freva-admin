FROM debian:bullseye-20240904

ARG VERSION
LABEL org.opencontainers.image.authors="DRKZ-CLINT"
LABEL org.opencontainers.image.source="https://github.com/freva-org/freva-deployment.git"
LABEL org.opencontainers.image.version="$VERSION"

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
    python3-appdirs \
    python3-mysqldb \
    python3-yaml \
    python3-toml \
    python3-tomlkit \
    python3-requests \
    python3-rich \
    python3-paramiko \
    python3-pymysql \
    ansible \
    python3-mock \
    mysql-common && \
    rm -rf /var/lib/apt/lists/*

# Set environment variables for locale
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Set up work directories
RUN mkdir -p /opt/freva-deployment /tmp/deployment /src

WORKDIR /tmp/deployment

# Copy all files into the container
COPY . .

# Install Python dependencies
RUN python3 src/freva_deployment/__init__.py && \
    python3 -m pip install pyinstaller rich-argparse namegenerator npyscreen && \
    python3 -m pip install --no-deps . &&\
    rm -rf /root/.cache/pip && \
    rm -rf /root/build-deps && \
    rm -rf /tmp/deployment

WORKDIR /opt/freva-deployment

# Define volumes
VOLUME /opt/freva-deployment
VOLUME /src

# Define the default command
CMD ["/usr/local/bin/deploy-freva"]
