---
id: n64-native-ports
title: Nintendo 64 through native ports
sidebar_position: 10
---

# Nintendo 64 through native ports

There is no Nintendo 64 emulator for the ESP32-S3 and there will not be one: the
console is out of reach of this chip. Two of its games have been decompiled to
C, though, and a game compiled for the board is not emulated. That is the same
route as DOOM, Quake and Duke Nukem 3D here.

## Where we are

| Game | State (2026-10-05) |
|:---|:---|
| **Super Mario 64** | **runs on the board.** Title, demos and Peach's castle grounds were played by the user. No sound yet. Not installed: the flash has no room for it, so it is tested in the arcade app's slot and the arcade app is put back afterwards |
| **Mario Kart 64** | started the same day: the decompilation is imported, nothing builds for the board yet |

What was measured on Super Mario 64, and what was only seen:

- Title screen: 30 game frames per second (the game's own rate), 13 to 15 of them
  drawn. **Inside a level nothing has been measured yet.**
- By eye (the user playing): smooth at 160x120, about half as fast at 320x240,
  "ok, better" at 240x180. The 3D picture is drawn at that size and scaled to
  320x240; the HUD and text are always 320x240.
- Internal RAM free while it runs: 4 KB. PSRAM free: about 1.4 MB.
- App 1.38 MB, plus a 7.9 MB asset pack on the SD card.

## What was done

**Super Mario 64** (repo `pjcau/sm64-esp32`, private, submodule
`retro-go/sm64-go`). The starting point was an existing ESP32 port
(pcgamer404/retro-go-pro, itself from the FunKey port) that links every asset
into a 12 MB app. That does not fit a 16 MB flash shared with twelve other apps,
so the work was to take the assets out of the program:

1. A PC build of the port as a reference, dumping frames without a display; two
   runs give identical frames.
2. The decompilation's own segment system, switched back on: each asset segment
   (levels, actors, texture bins, skyboxes, behaviours, Mario's animations) is
   linked at its N64 segment address, kept out of the program image, and read
   from one pack file when a level asks for it. On the PC, 3000 frames (title
   and two demos) are identical to the reference, pixel for pixel, in 64-bit and
   32-bit builds.
3. The ESP32 build: the app and the segments are linked separately (they name
   each other: the app uses the assets' addresses, the assets hold the app's
   function addresses). App 11.6 MB → 1.38 MB.
4. First board run: title screen, then a crash at the first level load. The
   cause was in our own fast SD read (`rg_storage_fread_raw`), which returned
   data from the wrong place when internal RAM was too short for its buffer;
   fixed in the retro-go fork. After that the game played.

One command builds it from the user's ROM, in a work directory outside git:
`retro-go/sm64-go/build_esp32.sh <baserom.us.z64>` (`SM64_RENDER=WxH` for
another render size). **No ROM and no extracted asset is in any repository**; the
asset pack is built on the machine that has the ROM.

**Mario Kart 64** (repo `pjcau/mk64-esp32`, private, submodule
`retro-go/mk64-go`). Baseline: the n64decomp/mk64 decompilation, all C. Unlike
Super Mario 64 no port to a small machine exists (the PC port, SpaghettiKart, is
C++ on a GPU), so the PC layer has to be brought over from the Super Mario 64
port and the code that unpacks data for a big-endian console fixed first.

## What is left

| Item | Notes |
|:---|:---|
| Super Mario 64: measured speed inside a level, at the three render sizes | needs a session with the board in the arcade slot |
| Super Mario 64: a faster rasteriser, to make 240x180 or 320x240 worth it | only after the measurement says where the time goes |
| Super Mario 64: sound | 2.4 MB of sound data still to be read from the card; the app links a stand-in |
| Super Mario 64: internal RAM | 4 KB free is too little to rely on |
| Mario Kart 64: PC build, reference frames, assets on the card, board | the plan is in the repo's README |
| A place in the flash and a "Nintendo 64" section in the launcher | **decided by the user on 2026-10-05: wait for the 32 MB module** ([Plan D](/docs/next-steps/plan-esp32-s3-n32r16v)). No app is removed and the arcade game cache is not shrunk on the current board; until then N64 games are a temporary test |
