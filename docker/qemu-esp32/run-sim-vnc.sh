#!/bin/bash
# Run the native SDL2 simulator inside Docker with VNC access
set -e

ROM_DIR="${1:-/test-roms}"

echo "================================================"
echo "  ESP32 Emu Turbo — Simulator via VNC"
echo "  Browser: http://localhost:6080/vnc.html"
echo "  VNC:     vnc://localhost:5901"
echo "  Password: esp32"
echo "================================================"

# Start virtual X server
export DISPLAY=:99
Xvfb :99 -screen 0 960x640x24 &
sleep 1

# Start VNC server
x11vnc -display :99 -forever -passwd esp32 -listen 0.0.0.0 -rfbport 5901 -shared -bg -q

# Start noVNC web proxy
websockify --web /usr/share/novnc 6080 localhost:5901 &
sleep 1

echo "[VNC] Ready — connect now"

# Build simulator (clean macOS binaries first)
cd /project/sim
rm -f emu-turbo-sim test_all_cores test_screenshots
echo "[BUILD] Compiling simulator..."
make 2>&1 | tail -5

echo "[SIM] Launching emulator..."
exec ./emu-turbo-sim ${ROM_DIR}
