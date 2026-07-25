# ESP32 Emu Turbo - JLCPCB BOM Summary

## SMT Components (assembled by JLCPCB)

| Ref | Component | Package | LCSC | Type | Qty | Unit $ |
|-----|-----------|---------|------|------|-----|--------|
| U1 | ESP32-S3-WROOM-1-N16R8 | Module | C2913202 | Extended | 1 | ~$3.50 |
| U2 | IP5306 (charger+boost) | ESOP-8 | C181692 | Extended | 1 | ~$0.35 |
| U3 | SY8089AAAC (2A synchronous buck) | SOT-23-5 | C78988 | Extended | 1 | ~$0.13 |
| U5 | PAM8403 (audio amp) | SOP-16 | C5122557 | Extended | 1 | ~$0.50 |
| J1 | USB-C 16-pin connector | SMD | C2765186 | Extended | 1 | ~$0.07 |
| U6 | Micro SD card slot | TF-01A | C91145 | Extended | 1 | ~$0.19 |
| J4 | FPC 40-pin 0.5mm | SMD | TBD | Extended | 1 | ~$0.10 |
| J3 | JST PH 2-pin (battery) | SMD | C295747 | Basic | 1 | ~$0.04 |
| L1 | 1uH inductor (IP5306 boost) | 4x4x2mm | C280579 | Extended | 1 | ~$0.25 |
| L2 | 2.2uH inductor (buck output, Isat 2.95A) | 4x4mm | C36409 | Extended | 1 | ~$0.11 |
| R1-R2 | 5.1k (CC pull-down) | 0805 | C27834 | Basic | 2 | ~$0.002 |
| R4-R15 | 10k (pull-ups) | 0805 | C17414 | Basic | 11 | ~$0.002 |
| R16,R24,R25 | 100k (KEY pull-up, Q1 gate, buck FB upper) | 0805 | C149504 | Basic | 3 | ~$0.002 |
| R26 | 22k (buck FB lower) | 0805 | C17560 | Basic | 1 | ~$0.002 |
| R17-R18 | 1k (LED limiting) | 0805 | C17513 | Basic | 2 | ~$0.002 |
| R20-R21 | 20k (PAM8403 INL/INR bias) | 0805 | C4328 | Basic | 2 | ~$0.002 |
| C3-C16,C21 | 100nF (decoupling) | 0805 | C49678 | Basic | 16 | ~$0.002 |
| C22 | 0.47uF (PAM8403 DC-block) | 0805 | C13967 | Basic | 1 | ~$0.005 |
| C23-C25 | 1uF (PAM8403 VDD/PVDD) | 0805 | C28323 | Basic | 3 | ~$0.005 |
| C17,C18,C27 | 10uF | 0805 | C15850 | Basic | 3 | ~$0.01 |
| C1,C19,C30 | 22uF MLCC (buck C_IN/C_OUT, IP5306 bulk) | 1206 | C12891 | Basic | 3 | ~$0.02 |
| C29 | 22pF C0G (buck FB feed-forward) | 0805 | C1804 | Basic | 1 | ~$0.004 |
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

**Basic parts (no extra fee):** 5.1k, 10k, 22k, 100k resistors,
22pF/100nF/10uF/22uF capacitors

**Extended parts ($3 each):** ESP32-S3, IP5306, SY8089AAAC, PAM8403,
USB-C connector, SD card slot, FPC connector, JST PH, L1/L2 inductors,
tact switches

> **C2 (22uF tantalum) removed.** It was the AMS1117 output cap and it
> destroyed prototype #1 when assembled reversed
> (`website/docs/rework/incident-c2-reversed.md`). The SY8089 buck uses
> C30, a non-polarized 22uF MLCC, so the most dangerous polarized part on
> the board no longer exists.
