#!/usr/bin/env bash

CONFIG_DIR=${CONFIG_DIR:-/config}

mkdir -p $CONFIG_DIR
if [ ! -f /config/evaluation_system.conf ]; then
     printf '%s' "$VAR1_B64" | base64 -d > /config/evaluation_system.conf
fi

if [ ! -f /config/web/freva_web.toml ]; then
     mkdir -p /config/web
     printf '%s' "$VAR2_B64" | base64 -d > /config/web/freva_web.toml
fi
