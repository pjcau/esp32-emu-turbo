---
id: intro
title: ESP32 Emu Turbo
sidebar_position: 1
slug: /
---

# ESP32 Emu Turbo

Handheld gaming console based on **ESP32-S3** for retro game emulation — **SNES** (primary) and **NES** (secondary).

## Goal

Build a portable battery-powered device with USB-C charging and an ILI9488 3.95" color LCD display, capable of loading and playing retro games from an SD card.

## Development Phases

| Phase | Description | Status |
|---|---|---|
| **1. Feasibility** | Component analysis, schematics, budget | Completed |
| **2. Hardware Design** | KiCad schematics, OpenSCAD enclosure, GPIO mapping | In Progress |
| **3. Prototype** | Breadboard assembly, testing and validation | Pending |
| **4. Final version** | Custom PCB + 3D-printed enclosure | Pending |

## Key Requirements

| Component | Specification |
|---|---|
| **MCU** | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM) |
| **Display** | ILI9488 3.95" 320x480, bare panel + 40P FPC 0.5mm |
| **Power** | LiPo 3.7V, 5000mAh |
| **Charging** | USB-C (IP5306, charge-and-play) |
| **Emulation** | SNES (primary), NES (secondary) |
| **Budget** | ~$42-55 for the prototype |

## Documentation

| Section | Content |
|---|---|
| [Design](/docs/design/schematics) | Schematics, components, PCB layout, GPIO mapping |
| [Manufacturing](/docs/manufacturing/manufacturing) | JLCPCB ordering, BOM, CPL, DFM verification |
| [Software](/docs/software/software) | ESP-IDF firmware, SNES optimization, audio profiles |
| [Development](/docs/development/workflow-guide) | **Agent & Skill Workflow Guide** — how to use 43 skills and 6 agents |
| [Tooling](/docs/tooling/docker) | Docker, rendering, build infrastructure |
