---
id: intro
title: ESP32 Emu Turbo
sidebar_position: 1
slug: /
---

# ESP32 Emu Turbo

Handheld gaming console based on **ESP32-S3** for retro game emulation (**NES**, and potentially **SNES**).

## Goal

Build a portable battery-powered device with USB-C charging and a 3.5"-4" color TFT/LCD display, capable of loading and playing retro games from an SD card.

## Development Phases

| Phase | Description | Status |
|---|---|---|
| **1. Feasibility** | Component analysis, schematics, budget | Completed |
| **2. Prototype** | Breadboard assembly, testing and validation | Pending |
| **3. Final version** | Custom PCB + 3D-printed enclosure | Pending |

## Key Requirements

| Component | Specification |
|---|---|
| **MCU** | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM) |
| **Display** | Color TFT/LCD, 3.5"-4" (ST7796S or ILI9488) |
| **Power** | LiPo 3.7V, 5000mAh |
| **Charging** | USB-C (IP5306, charge-and-play) |
| **Emulation** | NES (primary), SNES (secondary) |
| **Budget** | ~$42-55 for the prototype |
