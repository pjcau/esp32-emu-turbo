#!/usr/bin/env bash
# setup-sdcard.sh — Format SD card as FAT32 and copy test ROMs
#
# Usage:
#   ./scripts/setup-sdcard.sh /dev/sdX          # format + copy
#   ./scripts/setup-sdcard.sh /dev/sdX --no-format  # copy only (skip format)
#
# WARNING: This script will ERASE ALL DATA on the specified device!

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ROMS_SRC="$PROJECT_DIR/test-roms"

# Retro-Go expected folder names on SD card
ROM_DIRS=(nes gb gbc sms gg pce gen snes)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <device> [--no-format]"
    echo ""
    echo "  <device>      SD card device (e.g. /dev/sdb, /dev/mmcblk0)"
    echo "  --no-format   Skip formatting, only copy ROMs"
    echo ""
    echo "Examples:"
    echo "  $0 /dev/sdb              # Format FAT32 + copy ROMs"
    echo "  $0 /dev/mmcblk0          # Format FAT32 + copy ROMs"
    echo "  $0 /dev/sdb --no-format  # Copy ROMs only (SD already formatted)"
    exit 1
}

# --- Argument parsing ---
if [ $# -lt 1 ]; then
    usage
fi

DEVICE="$1"
DO_FORMAT=true

if [ "${2:-}" = "--no-format" ]; then
    DO_FORMAT=false
fi

# --- Safety checks ---
if [ ! -b "$DEVICE" ]; then
    echo -e "${RED}Error: $DEVICE is not a block device${NC}"
    exit 1
fi

# Prevent accidental formatting of system disks
ROOTDEV=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/[0-9]*$//' | sed 's/p[0-9]*$//')
if [ "$DEVICE" = "$ROOTDEV" ]; then
    echo -e "${RED}Error: $DEVICE appears to be your system disk. Aborting!${NC}"
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
    echo "  sudo $0 $*"
    exit 1
fi

# --- Check source ROMs exist ---
if [ ! -d "$ROMS_SRC" ]; then
    echo -e "${RED}Error: test-roms/ directory not found at $ROMS_SRC${NC}"
    echo "Run this script from the project root."
    exit 1
fi

ROM_COUNT=$(find "$ROMS_SRC" -type f | wc -l)
if [ "$ROM_COUNT" -eq 0 ]; then
    echo -e "${RED}Error: No ROM files found in $ROMS_SRC${NC}"
    exit 1
fi

echo -e "${YELLOW}=== ESP32 Emu Turbo — SD Card Setup ===${NC}"
echo ""
echo "  Device:    $DEVICE"
echo "  Format:    $DO_FORMAT"
echo "  ROMs:      $ROM_COUNT files from test-roms/"
echo ""

# --- Confirmation ---
echo -e "${RED}WARNING: This will ERASE ALL DATA on $DEVICE${NC}"
read -rp "Type 'yes' to continue: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# --- Unmount any existing partitions ---
echo ""
echo -e "${GREEN}[1/4] Unmounting existing partitions...${NC}"
for part in "${DEVICE}"*; do
    if mountpoint -q "$part" 2>/dev/null || mount | grep -q "$part"; then
        umount "$part" 2>/dev/null || true
        echo "  Unmounted $part"
    fi
done

# --- Format as FAT32 ---
if [ "$DO_FORMAT" = true ]; then
    echo -e "${GREEN}[2/4] Creating partition table and FAT32 filesystem...${NC}"

    # Create MBR partition table with single FAT32 partition
    parted -s "$DEVICE" mklabel msdos
    parted -s "$DEVICE" mkpart primary fat32 1MiB 100%

    # Determine partition device name
    sleep 1  # wait for kernel to re-read partition table
    if [ -b "${DEVICE}1" ]; then
        PARTITION="${DEVICE}1"
    elif [ -b "${DEVICE}p1" ]; then
        PARTITION="${DEVICE}p1"
    else
        echo -e "${RED}Error: Could not find partition after formatting${NC}"
        exit 1
    fi

    # Format as FAT32 with label
    mkfs.vfat -F 32 -n "RETRO-GO" "$PARTITION"
    echo "  Created FAT32 partition: $PARTITION"
else
    echo -e "${GREEN}[2/4] Skipping format (--no-format)${NC}"
    # Find existing partition
    if [ -b "${DEVICE}1" ]; then
        PARTITION="${DEVICE}1"
    elif [ -b "${DEVICE}p1" ]; then
        PARTITION="${DEVICE}p1"
    else
        PARTITION="$DEVICE"
    fi
fi

# --- Mount SD card ---
echo -e "${GREEN}[3/4] Mounting SD card...${NC}"
MOUNT_POINT=$(mktemp -d /tmp/sdcard-XXXXXX)
mount "$PARTITION" "$MOUNT_POINT"
echo "  Mounted $PARTITION at $MOUNT_POINT"

# --- Create directories and copy ROMs ---
echo -e "${GREEN}[4/4] Creating ROM directories and copying files...${NC}"

# Create Retro-Go directory structure
mkdir -p "$MOUNT_POINT/roms"
for dir in "${ROM_DIRS[@]}"; do
    mkdir -p "$MOUNT_POINT/roms/$dir"
done

# Copy ROM files from test-roms/ to SD card
COPIED=0
for dir in "${ROM_DIRS[@]}"; do
    if [ -d "$ROMS_SRC/$dir" ]; then
        for rom in "$ROMS_SRC/$dir"/*; do
            if [ -f "$rom" ]; then
                cp "$rom" "$MOUNT_POINT/roms/$dir/"
                echo "  roms/$dir/$(basename "$rom")"
                COPIED=$((COPIED + 1))
            fi
        done
    fi
done

# --- Sync and unmount ---
echo ""
echo "Syncing..."
sync
umount "$MOUNT_POINT"
rmdir "$MOUNT_POINT"

echo ""
echo -e "${GREEN}Done! $COPIED ROM(s) copied to SD card.${NC}"
echo ""
echo "SD card directory structure:"
echo "  /roms/"
for dir in "${ROM_DIRS[@]}"; do
    echo "  /roms/$dir/"
done
echo ""
echo "Insert the SD card into your ESP32 Emu Turbo and power on."
