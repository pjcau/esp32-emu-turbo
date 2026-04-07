#!/bin/bash
# ESP32 Emu Turbo — SDL2 Simulator (Docker)
#
# Usage:
#   ./scripts/sim-run.sh build    # Build Docker image + compile test
#   ./scripts/sim-run.sh test     # Run simulator test (VNC on port 5900)
#   ./scripts/sim-run.sh shell    # Open shell in container
#
# Connect display: open vnc://localhost:5900

set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="esp32-emu-turbo-sim"

ensure_image() {
    if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
        echo "Building simulator Docker image..."
        docker build -t "$IMAGE" docker/simulator/
    fi
}

case "${1:-help}" in
    build)
        echo "Compiling simulator (native macOS)..."
        cd software/sim
        gcc -DSIM_BUILD -o sim_test_native sim_test.c sim_hal.c \
            $(sdl2-config --cflags --libs) -lm 2>&1
        echo "Build OK: software/sim/sim_test_native"
        ;;

    run)
        if [ ! -f software/sim/sim_test_native ]; then
            echo "No binary. Building..."
            "$0" build
        fi
        mkdir -p roms
        echo ""
        echo "ESP32 Emu Turbo — Simulator"
        echo "==========================="
        echo ""
        echo "  D-pad:   W/A/S/D"
        echo "  A/B:     J/K"
        echo "  X/Y:     U/I"
        echo "  Start:   Enter"
        echo "  Select:  Backspace"
        echo "  L/R:     Q/E"
        echo "  Quit:    ESC"
        echo ""
        exec software/sim/sim_test_native roms
        ;;

    docker)
        ensure_image
        echo "Starting simulator in Docker with VNC on port 5900..."
        echo "Connect: open vnc://localhost:5900"
        docker run --rm -v "$(pwd)":/project -w /project/software/sim \
            esp32-emu-turbo-sim bash -c \
            'gcc -DSIM_BUILD -o sim_test sim_test.c sim_hal.c $(sdl2-config --cflags --libs) -lm'
        mkdir -p roms
        docker run --rm -it \
            -v "$(pwd)":/project \
            -w /project/software/sim \
            -p 5900:5900 \
            "$IMAGE" \
            /usr/local/bin/start-vnc.sh ./sim_test /project/roms
        ;;

    help|*)
        echo "ESP32 Emu Turbo — SDL2 Simulator"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "  build    Compile simulator (requires: brew install sdl2)"
        echo "  run      Run simulator (native macOS window)"
        echo "  docker   Run in Docker with VNC (port 5900)"
        echo ""
        ;;
esac
