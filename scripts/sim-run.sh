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
        echo "Building simulator Docker image..."
        docker build -t "$IMAGE" docker/simulator/
        echo ""
        echo "Compiling sim_test inside container..."
        docker run --rm \
            -v "$(pwd)":/project \
            -w /project/software/sim \
            "$IMAGE" \
            gcc -DSIM_BUILD -o sim_test sim_test.c sim_hal.c \
                $(docker run --rm "$IMAGE" sdl2-config --cflags --libs) -lm
        echo "Build OK: software/sim/sim_test"
        ;;

    test)
        ensure_image
        if [ ! -f software/sim/sim_test ]; then
            echo "No binary found. Building..."
            "$0" build
        fi
        echo ""
        echo "Starting simulator with VNC display on port 5900..."
        echo "Connect: open vnc://localhost:5900"
        echo "Controls: WASD=D-pad, JK=AB, UI=XY, Enter=Start, Backspace=Select, QE=LR"
        echo "Press ESC to exit."
        echo ""
        mkdir -p roms
        docker run --rm -it \
            -v "$(pwd)":/project \
            -w /project/software/sim \
            -p 5900:5900 \
            "$IMAGE" \
            /usr/local/bin/start-vnc.sh ./sim_test /project/roms
        ;;

    shell)
        ensure_image
        docker run --rm -it \
            -v "$(pwd)":/project \
            -w /project \
            -p 5900:5900 \
            "$IMAGE" bash
        ;;

    help|*)
        echo "ESP32 Emu Turbo — SDL2 Simulator"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "  build   Build Docker image + compile simulator"
        echo "  test    Run simulator (VNC display on port 5900)"
        echo "  shell   Open shell in container"
        echo ""
        echo "Display: connect VNC to localhost:5900"
        echo "Controls: WASD=D-pad, JK=AB, UI=XY, Enter=Start"
        ;;
esac
