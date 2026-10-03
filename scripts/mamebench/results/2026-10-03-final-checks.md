# Final checks 2026-10-03: fork 0423ff54 on every app

Board: every app and the launcher built from retro-go fork 0423ff54 (loading
percentage in every emulator, the per-format scaler of b093d776). mame-go is the
play build `NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 AUDIO_MIX_HZ=16000`
(20 MHz LCD bus, 16 kHz chips doubled to the 32 kHz output, "MAMEBENCH frames"
count 0). All builds compiled without errors or warnings in the touched files;
`components/retro-go/test/run_scale_line_test.sh`: PASS (2400 cases).
Checks by console + webcam (C920 in front of the board) + C920 microphone.

## Smoke check, one game per app

| app | game | loading percentage | picture | sound (mic RMS, room ~35 dB) | buttons | FPS |
|---|---|---|---|---|---|---|
| retro-core NES | owlia.nes (512 KB) | 12 -> 57 -> 94 % in ~1 s | ok | 51.7 dB | START opens the menu | - |
| retro-core SNES | Donkey Kong Country .sfc (4 MB) | climbs smoothly 1 -> 76 %+ over ~7 s | ok | 39.6 dB | (title) | 61 |
| gwenesis MD | miniplanets.bin (256 KB) | 25 %, 75 % | ok | 35.2 dB (not confirmed) | game started | 60 |
| gbsp GBA | Metal Slug Advance (8 MB) | **none**: bare hourglass ~8 s | ok, title | 43.2 dB | - | 60 |
| retro-core PCE | Street Fighter II' CE .zip | climbs smoothly 2 -> 88 % | ok, title menu | 45.1 dB | - | 60 |
| prboom-go | freedoom1.wad | **none**: bare hourglass ~5 s (own WAD loader) | ok, title then in game | 42.9 dB | in game | 35 |
| mame-go Neo Geo | mslug | bare ~1.5 s (P ROM inflated in one go), 36 -> 90 % smooth, then **stands at 90 % ~3 s** (regions to flash + machine init) | ok | 45.2 dB | coin/start ok | 62 |
| mame-go CPS1 | ffight | climbs 3 -> 99 % steadily | ok | 46.4 dB | intro only (see below) | 60 |

Launcher: no percentage anywhere.

## mame-go play build

| check | result |
|---|---|
| Metal Slug driven in play (filmed: in game 34-80 s, then GAME OVER) | **57.9 FPS, 19.3 drawn/s** (7.6 full + 11.7 partial), 38.6 skipped, BUSY 100 % — old build: 50.3 FPS / 16.8 drawn |
| Metal Slug attract, 4 min | 58.5 FPS (46-62), drawn 10.0+12.0 |
| Final Fight, turn skip on | 59.2 FPS, 21.7 drawn/s, 37.7 skipped |
| Final Fight, cps1_noturn | 51.7 FPS, 17.2 drawn/s, 34.5 skipped (file removed afterwards) |
| CPS1 saves (save / resume / in-session load) | cawing, ffight, ghouls, knights PASS (314164-byte states); **sf2ce, sf2hf FAIL**: in play PSRAM 77 KB free, largest block 68 KB, the 314 KB state cannot be allocated |
| Neo Geo save / resume / load (alpham2, webcam) | PASS |
| Lowest internal heap | Metal Slug 0-5 KB (HEAP:0 seen), Final Fight 18 KB |
| page_read DMA buffer | one-off NEOPROF build (9c920b47, played): sprite reads 6.9-7.3 ms, sample reads 3.3-5.5 ms, none at the old 12-17 ms: the buffer is obtained even with ~1 KB free reported |

Final Fight's console coin/start never left the intro story (also on the PC
harness: ffight/ghouls/knights "play" = attract), so its figures are the moving
intro, not play.

## Microphone, Metal Slug attract on the final play build

final_a / final_b: RMS -43.9 / -44.7 dBFS, clicks 13.4 / 11.4 per s, >8 kHz
0.02 %. Same as the bench builds of the afternoon (32 kHz -45.1 / -44.3, 16 kHz
-44.6 / -41.5; clicks 11-13/s). No dropout in 2 x 85 s. The play build's attract
is not frame-locked between takes (2 s profiles differ 3.8 dB mean between the
two takes of the same build), so only levels compare, not 2 s profiles.

## Not checked / open

- No "before" figures for the other emulators: they were not taken before the
  update; only after (all at their frame rate, picture right on the webcam).
- MD sound not confirmed (the title is quiet at the microphone).
- GBA and Doom show no loading percentage (own loaders).
- SF2 CE / HF save states: no PSRAM block large enough.
- Final Fight could not be driven into play from the console.
