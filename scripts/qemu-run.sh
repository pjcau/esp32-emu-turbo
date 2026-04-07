#!/bin/bash
# ESP32-S3 QEMU Simulator — Docker-based
#
# Usage:
#   ./scripts/qemu-run.sh build    # Build firmware for QEMU
#   ./scripts/qemu-run.sh run      # Run simulator (serial output)
#   ./scripts/qemu-run.sh shell    # Open shell in container
#   ./scripts/qemu-run.sh display  # Run with virtual display (VNC)
#
# Requires: Docker/OrbStack

set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="esp32-emu-turbo-qemu"
CONTAINER="esp32-qemu"
FIRMWARE_DIR="software"
BUILD_DIR="software/build"

# Build Docker image if not exists
ensure_image() {
    if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
        echo "Building QEMU Docker image (first time, ~5 min)..."
        docker build -t "$IMAGE" docker/qemu-esp32/
    fi
}

# Common docker run options
DOCKER_RUN="docker run --rm -it \
    -v $(pwd):/project \
    -w /project/software"

case "${1:-help}" in
    build)
        ensure_image
        echo "Building firmware for ESP32-S3 (QEMU target)..."
        $DOCKER_RUN "$IMAGE" bash -c "
            # Set target
            idf.py set-target esp32s3

            # Build
            idf.py build

            # Create merged flash image for QEMU
            esptool.py --chip esp32s3 merge_bin \
                --fill-flash-size 16MB \
                -o /project/software/build/flash_image.bin \
                @/project/software/build/flash_args

            echo '=== Flash image ready: software/build/flash_image.bin ==='
            ls -lh /project/software/build/flash_image.bin
        "
        ;;

    run)
        ensure_image
        if [ ! -f "$BUILD_DIR/flash_image.bin" ]; then
            echo "ERROR: No flash image. Run './scripts/qemu-run.sh build' first."
            exit 1
        fi
        echo "Starting QEMU ESP32-S3 (serial mode)..."
        echo "Press Ctrl+A then X to exit."
        $DOCKER_RUN "$IMAGE" \
            qemu-system-xtensa -nographic \
                -machine esp32s3 \
                -drive file=/project/software/build/flash_image.bin,if=mtd,format=raw \
                -m 8M \
                -global driver=ssi_psram,property=is_octal,value=true \
                -global driver=timer.esp32c3.timg,property=wdt_disable,value=true \
                -serial mon:stdio
        ;;

    display)
        ensure_image
        if [ ! -f "$BUILD_DIR/flash_image.bin" ]; then
            echo "ERROR: No flash image. Run './scripts/qemu-run.sh build' first."
            exit 1
        fi
        echo "Starting QEMU ESP32-S3 with VNC display on port 5900..."
        echo "Connect with: open vnc://localhost:5900"
        docker run --rm -it \
            -v "$(pwd)":/project \
            -w /project/software \
            -p 5900:5900 \
            "$IMAGE" \
            qemu-system-xtensa \
                -machine esp32s3 \
                -drive file=/project/software/build/flash_image.bin,if=mtd,format=raw \
                -m 8M \
                -global driver=ssi_psram,property=is_octal,value=true \
                -global driver=timer.esp32c3.timg,property=wdt_disable,value=true \
                -display vnc=:0 \
                -serial mon:stdio
        ;;

    shell)
        ensure_image
        echo "Opening shell in QEMU container..."
        $DOCKER_RUN "$IMAGE" bash
        ;;

    help|*)
        echo "ESP32-S3 QEMU Simulator"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  build    Build ESP-IDF firmware and create flash image"
        echo "  run      Run QEMU with serial output (Ctrl+A, X to exit)"
        echo "  display  Run QEMU with VNC display on port 5900"
        echo "  shell    Open interactive shell in container"
        echo ""
        echo "First run builds the Docker image (~5 min, ~4GB)."
        ;;
esac
