# Retro-Go Build Output

Pre-built firmware binaries for the ESP32 Emu Turbo target. Built with ESP-IDF v5.4 via Docker (`docker-compose.retro-go.yml`). Rebuilt 2026-09-14 (fork `8f3f0ad1`): console remote control, SNES renderer work, save-state loader fix, Genesis YM2612 on core 1, Debug HUD, SG-1000, Duke3D, NGP, Atari 2600. The partition table changed (retro-core 1.5 MB, + duke3d-go, + retro-extra): flash the full `.img` once, then single apps again.

## Binaries

| File | Contents | Size | Partition free |
|---|---|---|---|
| `launcher.bin` | Retro-Go launcher UI + ROM browser | 998 KB | 3% |
| `retro-core.bin` | All emulators (NES, GB, GBC, SMS, GG, PCE, Lynx, SNES, G&W) — production build, no SNES_PROF HUD | 973 KB | 5% |
| `gwenesis.bin` | Sega Genesis / Mega Drive (standalone) | 944 KB | 8% |
| `prboom-go.bin` | Doom port (PrBoom) | 796 KB | 22% |
| `fmsx.bin` | MSX emulator (fMSX) | 621 KB | 39% |
| `duke3d-go.bin` | Duke Nukem 3D (Chocolate Duke3D) — new 1 MB partition | 843 KB | 20% |
| `retro-extra.bin` | Neo Geo Pocket (RACE) + Atari 2600 (Stella) — new 2 MB partition | 1.5 MB | 29% |
| `retro-go_esp32-emu-turbo.img` | Full flash image (bootloader + partition table + all apps) — **required once** after the 2026-09-14 partition change: `esptool.py write_flash 0x0 retro-go_esp32-emu-turbo.img` (or `rg_tool.py install`) | 8.4 MB | — |

## How to flash

```bash
# From the project root
make retro-go-flash

# Or with a specific port
ESP_PORT=/dev/ttyACM0 make retro-go-flash
```

## How to rebuild

```bash
make retro-go-build
```

Then copy the new binaries:

```bash
cp retro-go/launcher/build/launcher.bin \
   retro-go/retro-core/build/retro-core.bin \
   retro-go/gwenesis/build/gwenesis.bin \
   retro-go/prboom-go/build/prboom-go.bin \
   retro-go/fmsx/build/fmsx.bin \
   software/retro-go-build/
```

## Build info

- **Target:** ESP32-EMU-TURBO (ESP32-S3 N16R8)
- **SDK:** ESP-IDF v5.4
- **Docker image:** `espressif/idf:v5.4`
- **Partition:** 3 MB app partition (single OTA slot)
