#!/bin/sh
APP_NAME=argo-decoder
BASEDIR=/app

echo "*** Starting ${APP_NAME} batch ***"
echo "This is V4"

# Ensure MATLAB Runtime cache folder exists and is writable
mkdir -p /mnt/runtime-cache
chown -R $(id -u):$(id -g) /mnt/runtime-cache
export MCR_CACHE_ROOT=/mnt/runtime-cache

# Set MATLAB Runtime library path
export LD_LIBRARY_PATH=/mnt/runtime/runtime/glnxa64:/mnt/runtime/bin/glnxa64:/mnt/runtime/sys/os/glnxa64:/mnt/runtime/sys/opengl/lib/glnxa64:$LD_LIBRARY_PATH

# Debug info: list app contents
echo "Contents of /app:"
ls -l /app

# Debug info: find the decoder binary
echo "Searching for decode_argo_2_nc_rt..."
find /app -type f -name "decode_argo_2_nc_rt" -executable

# Run decoder via wrapper script
if [ -x /app/run_decode_argo_2_nc_rt.sh ]; then
    /app/run_decode_argo_2_nc_rt.sh /mnt/runtime rsynclog all configfile /mnt/data/config/decoder_conf.json \
        xmlreport co041404_20250919T122855Z_6902892.xml \
        floatwmo 6902892 PROCESS_REMAINING_BUFFERS 1
else
    echo "[ERROR] Wrapper script /app/run_decode_argo_2_nc_rt.sh not found or not executable!"
    exit 1
fi
