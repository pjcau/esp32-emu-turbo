# ESP32 Emu Turbo - JLCPCB BOM Summary

## SMT Components (assembled by JLCPCB)

| Ref | Component | Package | LCSC | Type | Qty | Unit $ |
|-----|-----------|---------|------|------|-----|--------|
| U1 | ESP32-S3-WROOM-1-N16R8 | Module | C2913202 | Extended | 1 | ~$3.50 |
| U2 | IP5306 (charger+boost) | ESOP-8 | C181692 | Extended | 1 | ~$0.35 |
| U3 | AMS1117-3.3 (LDO) | SOT-223 | C6186 | Basic | 1 | ~$0.05 |
| U5 | PAM8403 (audio amp) | SOP-16 | C5122557 | Extended | 1 | ~$0.50 |
| J1 | USB-C 16-pin connector | SMD | C2765186 | Extended | 1 | ~$0.07 |
| U6 | Micro SD card slot | TF-01A | C91145 | Extended | 1 | ~$0.19 |
| J4 | FPC 40-pin 0.5mm (XUNPU) | SMD | C2856812 | Extended | 1 | ~$0.08 |
| J3 | JST PH 2-pin (battery) | THT | C173752 | Extended | 1 | ~$0.04 |
| L1 | 1uH inductor (boost) | 4x4x2mm | C280579 | Extended | 1 | ~$0.25 |
| R1-R2 | 5.1k (CC pull-down) | 0805 | C27834 | Basic | 2 | ~$0.002 |
| R3-R15,R19 | 10k (pull-ups) | 0805 | C17414 | Basic | 14 | ~$0.002 |
| R16 | 100k (KEY pull-up) | 0805 | C149504 | Basic | 1 | ~$0.002 |
| R17-R18 | 1k (LED limiting) | 0805 | C11702 | Basic | 2 | ~$0.002 |
| C3-C16,C20 | 100nF (decoupling) | 0805 | C49678 | Basic | 15 | ~$0.002 |
| C1,C17,C18 | 10uF | 0805 | C15850 | Basic | 3 | ~$0.01 |
| C2,C19 | 22uF (tantalum/MLCC) | 1206 | C29632 | Basic | 2 | ~$0.02 |
| SW1-SW13 | SMT tact switch | 5.1x5.1mm | C318884 | Extended | 13 | ~$0.02 |

## Manual Assembly (not on PCB or off-board)

| Component | Notes |
|-----------|-------|
| LiPo Battery 3.7V 5000mAh | Plugs into J3 JST PH connector |
| ILI9488 3.95" Bare LCD Panel | Connects via J4 FPC-40P ribbon cable |
| 28mm 8ohm Speaker | Solder to pads or 2-pin header |
| PSP Joystick (optional) | Pin header on PCB |

## Cost Estimate (5 boards)

| Item | Cost |
|------|------|
| PCB fabrication (4-layer, 160x75mm, 5pcs) | ~$20 |
| SMT setup fee | ~$8 |
| Extended part fees (9 unique x $3) | $27 |
| Components (LCSC, 5 boards) | ~$35 |
| Assembly labor | ~$5 |
| **Total (5 boards)** | **~$95** |
| **Per board** | **~$19** |

## JLCPCB Part Classification

**Basic parts (no extra fee):** AMS1117-3.3, 5.1k, 10k, 100k resistors,
100nF/10uF/22uF capacitors

**Extended parts ($3 each):** ESP32-S3, IP5306, PAM8403, USB-C connector,
SD card slot, FPC connector, JST PH, inductor, tact switches
