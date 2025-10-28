#!/usr/bin/env bash
set -xe

CONFIG_DIR=${FREVA_CONFIG:-/config}

mkdir -p $CONFIG_DIR
if [ ! -f ${CONFIG_DIR}/evaluation_system.conf ]; then
     printf '%s' "$VAR1_B64" | base64 -d > ${CONFIG_DIR}/evaluation_system.conf
fi

if [ ! -f ${CONFIG_DIR}/web/freva_web.toml ]; then
     mkdir -p ${CONFIG_DIR}/web
     printf '%s' "$VAR2_B64" | base64 -d > ${CONFIG_DIR}/web/freva_web.toml
fi
