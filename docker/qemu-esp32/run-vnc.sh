#!/bin/bash
# Launch QEMU ESP32-S3 with VNC display via Xvfb + x11vnc
# Connect with VNC client to localhost:5900

set -e

FLASH_IMAGE="${1:-/project/benchmark/build/flash_image.bin}"
PSRAM_SIZE="${2:-32M}"
VNC_PORT="${3:-5900}"

echo "================================================"
echo "  QEMU ESP32-S3 with VNC Display"
echo "  Connect: vnc://localhost:${VNC_PORT}"
echo "  UART:    serial output on stdout"
echo "  Input:   send keys via UART (stdin)"
echo "================================================"

# Start virtual X server
export DISPLAY=:99
Xvfb :99 -screen 0 640x480x24 &
XVFB_PID=$!
sleep 1

# Start VNC server (password: esp32)
x11vnc -display :99 -forever -passwd esp32 -listen 0.0.0.0 -rfbport 5901 -shared -bg -q

# Start noVNC web proxy (browser access)
websockify --web /usr/share/novnc 6080 localhost:5901 &

echo ""
echo "[VNC]    vnc://localhost:5901"
echo "[BROWSER] http://localhost:6080/vnc.html"
echo ""

# Launch QEMU with SDL display on virtual X server
exec qemu-system-xtensa \
    -machine esp32s3 \
    -display sdl \
    -m ${PSRAM_SIZE} \
    -global driver=ssi_psram,property=is_octal,value=true \
    -drive file=${FLASH_IMAGE},if=mtd,format=raw \
    -global driver=timer.esp32.timg,property=wdt_disable,value=true \
    -serial mon:stdio \
    -no-reboot
