# Retro-Go Build Output

Pre-built firmware binaries for the ESP32 Emu Turbo target. Built with ESP-IDF v5.4 via Docker (`docker-compose.retro-go.yml`).

## Binaries

| File | Contents | Size | Partition free |
|---|---|---|---|
| `launcher.bin` | Retro-Go launcher UI + ROM browser | 1015 KB | 67% |
| `retro-core.bin` | All emulators (NES, GB, GBC, SMS, GG, PCE, Lynx, SNES, G&W, MSX) | 972 KB | ~68% |
| `gwenesis.bin` | Sega Genesis / Mega Drive (standalone) | 962 KB | ~69% |
| `prboom-go.bin` | Doom port (PrBoom) | 814 KB | ~74% |
| `fmsx.bin` | MSX emulator (fMSX) | 639 KB | 79% |

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
