# N64 flash layout installed, 2026-10-06

Full image written (fork e24e8ffe layout, mame-go play flags NB_LINES=16 LCD_BUFS=3
BAND_INTERNAL=3 NEOBAND=2 AUDIO_MIX_HZ=16000), after a full backup of the previous
flash (~/flash-backups/flash-2026-10-05-before-n64.bin, sha1
dd7593978771103dde023f87c19dbd9541b718cd). Then sm64-go updated through the SD
updater to the sound build (sm64-esp32 792ea01, pack 10302480 bytes, 137 segments,
build id af277fd6). Launcher art for the Nintendo 64 tab: fork 4071145e.

## Partition table as flashed (read back from 0x8000)

| name | type | offset | size |
|---|---|---|---|
| nvs | data 02 | 0x009000 | 16 KB |
| otadata | data 00 | 0x00d000 | 8 KB |
| phy_init | data 01 | 0x00f000 | 4 KB |
| launcher | app 10 | 0x010000 | 1152 KB |
| retro-core | app 11 | 0x130000 | 1280 KB |
| prboom-go | app 12 | 0x270000 | 832 KB |
| gwenesis | app 13 | 0x340000 | 1024 KB |
| sm64-go | app 14 | 0x440000 | 1792 KB |
| retro-extra | app 15 | 0x600000 | 1280 KB |
| mame-go | app 16 | 0x740000 | 2048 KB |
| wolf3d-go | app 17 | 0x940000 | 640 KB |
| gbsp | app 18 | 0x9e0000 | 832 KB |
| opentyrian-go | app 19 | 0xab0000 | 640 KB |
| cannonball | app 1a | 0xb50000 | 640 KB |
| mamerom | data 40 | 0xbf0000 | 4096 KB |

## Checks (webcam on each)

1. Arcade: Metal Slug from the launcher, coin + START -> "HOW TO PLAY"; Final Fight
   (CPS1) intro; Pac-Man attract. The first arcade start rewrote the game cache.
2. One game each: Super Mario World (retro-core), miniplanets (gwenesis), Metal Slug
   Advance (gbsp), Freedoom (prboom-go), Wolfenstein 3D, OpenTyrian, OutRun, Arcade 3D:
   all start.
3. Launcher tabs (cycled with START): no Duke Nukem 3D, no Quake; a Nintendo 64 tab
   with its banner and logo, listing "Super Mario 64". No cover for the game yet.
4. Super Mario 64 from the N64 tab with sound (volume 10 for the check, 0 after):
   title, START, file A, Peach's letter, the Lakitu intro. Sound present on the mic
   (-46 dBFS title, -43 intro, against about -68 silence), 0 clicks. With sound on the
   game runs at 16.2 ticks/s on the title (27.9 without sound) and 16.6 in the intro.
   Internal RAM 73 KB free, PSRAM 692 KB in the intro. No crash.
