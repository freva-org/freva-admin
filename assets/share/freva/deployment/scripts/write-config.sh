#!/usr/bin/env bash
set -xe

CONFIG_DIR=${FREVA_CONFIG:-/config}

mkdir -p $CONFIG_DIR
if [ ! -f /config/evaluation_system.conf ]; then
     printf '%s' "$VAR1_B64" | base64 -d > /config/evaluation_system.conf
fi

if [ ! -f /config/web/freva_web.toml ]; then
     mkdir -p /config/web
     printf '%s' "$VAR2_B64" | base64 -d > /config/web/freva_web.toml
fi
