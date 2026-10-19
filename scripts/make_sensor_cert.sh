#!/bin/sh
# HTTPS cert for the phone sensor page (iOS only allows getUserMedia on HTTPS).
# Preferred: Tailscale (real trusted cert).   Usage: scripts/make_sensor_cert.sh [tailscale-hostname]
# Without an argument, makes a self-signed cert (must be installed and trusted on the iPhone).
set -e
cd "$(dirname "$0")/.."
mkdir -p data/certs
if [ -n "$1" ]; then
  tailscale cert --cert-file data/certs/sensor.crt --key-file data/certs/sensor.key "$1"
else
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=oscar.local" \
    -addext "subjectAltName=DNS:oscar.local" \
    -keyout data/certs/sensor.key -out data/certs/sensor.crt
fi
echo "wrote data/certs/sensor.{crt,key}"
