#!/bin/bash

# Define Decoder image to use
export DECODER_IMAGE_TAG=${2:-"066a"}

# User uid and gid from the current user
export USER_ID=$UID
export GROUP_ID=$(id -g $UID)

export FLOAT_WMO=$1
if [[ -z "${FLOAT_WMO}" ]]; then
    echo "[ERROR] FLOAT_WMO required ! please execute script with FLOAT_WMO as parameter." >&2
    exit 1
fi
export DECODER_COMMAND=$(echo /mnt/runtime 'rsynclog' 'all' 'configfile' '/mnt/data/config/decoder_conf.json' 'xmlreport' 'co041404_'$(date +"%Y%m%dT%H%M%SZ")'_'$FLOAT_WMO'.xml' 'floatwmo' ''$FLOAT_WMO'' 'PROCESS_REMAINING_BUFFERS' '1')

docker compose -f compose.yaml -f compose.matlab-runtime.yaml down
docker compose -f compose.yaml -f compose.matlab-runtime.yaml up