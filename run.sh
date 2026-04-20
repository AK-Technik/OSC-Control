#!/usr/bin/with-contenv bashio

CONFIG_PATH=$(bashio::config 'config_path')
HA_TOKEN=$(bashio::config 'ha_token')

export CONFIG_PATH="${CONFIG_PATH:-/config/ha-showcontrol}"
export HA_TOKEN="${HA_TOKEN}"
export HA_URL="http://supervisor/core"

mkdir -p "${CONFIG_PATH}/profiles"
mkdir -p "${CONFIG_PATH}/library"

exec python3 /app/main.py
