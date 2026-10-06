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

| Game | State (2026-10-06) |
|:---|:---|
| **Super Mario 64** | **runs on the board, in the launcher, with sound, at the game's full speed**: 30 ticks a second on the title, in the demos and in the castle grounds, about 6 frames drawn a second at 320x240. Open: more drawn frames (see below: at this size it is the arithmetic of every pixel) |
| **Mario Kart 64** | **runs on the board, in the launcher, without sound**: title 8 frames a second, menus 7 to 9, a race 3 to 4 (Luigi Raceway). Colours right. In a race all the time is drawing. Still wrong: the portraits on player select, the course previews. On a PC: the logo, the title, the demo race and, with a scripted pad, a Grand Prix race from the menus |

What was measured on Super Mario 64 (board; the 3D picture is drawn at the size
given and the HUD and text are always 320x240):

| Render size | Build | Scene | Game ticks per second (30 = full speed) | Drawn frames per second |
|:---|:---|:---|:---|:---|
| 160x120 | first build, 2026-10-05, no sound | castle grounds | 28.3 | 7.4 |
| 320x240 | first build, no sound | castle grounds | 14.5 | 3.6 |
| 320x240 | render task on the second core, no sound (the build the user played and liked) | castle grounds | 30.5 | 4.1 |
| 320x240 | the same | title | 27.9 | 7.0 |
| **320x240** | **2026-10-06, with sound, installed** | castle grounds | **30.0** | **6.0** |
| **320x240** | the same | Bowser demo (music) | **30.4** | **6.4** |
| **320x240** | the same | title (music) | **29.4** | **6.4** |
| **320x240** | the same | Bob-omb Battlefield (music), standing and running | **30.0** | **6.0 to 6.2** |
| 240x180 | 2026-10-06, with sound, second core not helping | castle grounds | 30.0 | 7.5 |
| 160x120 | the same | castle grounds | 30.0 | 10.5 |

- 30 ticks a second is the game's own full speed: there is nothing above it.
  What can still rise is the number of frames drawn, and it rises in steps: a
  new frame starts with a game tick, so a frame that takes under 133 ms gives
  7.5 a second and one under 100 ms gives 10. At 320x240 a frame of the castle
  grounds takes about 150 ms (rasteriser 120 to 130, display list 20).
- Sound: plays from the pack on the card. Where there is music the synthesis
  takes 4 to 14 ms of each tick (4 to 6.5 in Bob-omb Battlefield, about 8 on
  the title, 12 to 14 in the Bowser demo; the title was at 12 before the
  mixer's loops were rewritten; 2.5 ms in the castle grounds, which have no
  music); the game holds 30 ticks with it everywhere it was measured. Not yet judged by ear: the board tests run at volume 0, and
  a microphone only confirms the sound is there.
- A hang on the way back to the launcher, found and fixed (2026-10-06). The
  last line was "Restarting system!", the game task stuck in the shutdown; a
  hard reset recovered it. The render task could send a frame to the display
  while the shutdown was clearing and closing it, and two streams to the panel
  at once hang its driver. The shutdown now stops frames first. Measured on
  the board with the same loop (start the game, 42 s into the Bowser demo,
  back to the launcher): 2 hangs in 20 with the old build, 0 in 30 with the
  fix; at the old rate 30 clean runs in a row would happen 4 times in 100.
- No crash in the cycles of title, demos and a walk through the castle grounds.
  Entering the castle (a level load during play) is not tested yet.
- Internal RAM free: 48 to 64 KB. External RAM free: 270 KB at least.
- App 1.6 MB, plus a 10.3 MB asset pack on the SD card.

Mario Kart 64 on the board (2026-10-06, 320x240, no sound, one core drawing):

| Place | Frames per second | Where the time goes |
|:---|:---|:---|
| Title | 8.2 to 8.4 | half rasteriser, half display list |
| Player select, map select | 7.3 to 8.6 | the same |
| A race, Luigi Raceway | 3.3 to 4.1 | rasteriser 220 to 250 ms of a 253 to 287 ms frame; the game's own logic is 7 ms |

The first builds ran a race at 1.3 frames a second: the game asks for the
karts' pictures all the time, a few hundred bytes from places far apart in the
pack, and every request was a 32 KB read of the SD card, 58 ms. The app now
keeps 128 blocks of 8 KB of the pack in memory. A race still starts slowly
while they fill: the first second after the course loads does about 70 card
reads (2.4 frames that second), then for some 25 s (the opening camera and the
line-up) a few reads a second of 15 ms each; after that it reads nothing.

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

5. Speed at 320x240, measured step by step on the board with a profile line the
   app logs once a second. What moved it: drawing the sky and other white-vertex
   triangles as plain texture (the sky alone was 77 of 220 ms), and above all
   **rendering on the second core**: the game task only builds each tick's
   display list and goes on ticking, a render task draws the newest one. What
   did not: removing the per-pixel division, integer arithmetic alone, inlining,
   hand-written pixel loops (a few percent each). A benchmark run on the board
   showed why: memory was never the cost (122 ns for the depth test and both
   stores, against 1000 ns a pixel for the sky).

6. With sound (2026-10-06), measured the same way:
   - The title ran at 24 ticks a second and it was not the sound: a frame of
     the title is drawn while the game waits (Mario's head), about 85 ms, so a
     turn of the main loop lasted five ticks' time, and the loop caught up at
     most four. With the limit at eight the title holds 30.
   - The sound mixer's two heaviest loops (sample decoding, volume envelope)
     were rewritten with the same arithmetic: the recorded sound of 3000 frames
     on the PC is identical to the byte, and the synthesis went from 12 to 8 ms
     a block on the title.
   - Drawing in bands on both cores, with the second core below the game in
     priority, did not add drawn frames, and three changes expected to help did
     not (the board's numbers said so each time): stepping to a band's first
     row in one multiplication instead of row by row, the sky drawn through
     the opaque shader instead of the alpha-blending one, the mixer's loops in
     internal RAM. The disassembly of the loop that draws a textured, shaded
     pixel is about 65 instructions: half a microsecond a pixel is arithmetic.
     At 320x240 the measured lever is the render size (table above).

One command builds it from the user's ROM, in a work directory outside git:
`retro-go/sm64-go/build_esp32.sh <baserom.us.z64>` (`SM64_RENDER=WxH` for
another render size). **No ROM and no extracted asset is in any repository**; the
asset pack is built on the machine that has the ROM.

**Mario Kart 64** (repo `pjcau/mk64-esp32`, private, submodule
`retro-go/mk64-go`). Baseline: the n64decomp/mk64 decompilation, all C. Unlike
Super Mario 64 no port to a small machine exists (the PC port, SpaghettiKart, is
C++ on a GPU), so the PC layer has to be brought over from the Super Mario 64
port and the code that unpacks data for a big-endian console fixed first.

What was done on it (2026-10-06):

| Step | Result |
|:---|:---|
| The game's data, native | the decompilation's own build steps run with a native 32-bit compiler: courses, common models, logo and ceremony compiled, linked alone at their segment address and MIO0-compressed as the game expects; kart frames and compressed textures taken as they are. One link lays everything out like the cartridge: `mk64.seg`, 8.6 MB |
| Checked against the ROM | where the bytes must be the same they are looked for, whole, in the ROM: the 20 packed display lists, the 20 courses' vertices (swapped back and compressed) and the kart, texture and menu segments are all found |
| The game keeps the console's way of loading | segment table, reads by ROM offset (now pack offset), MIO0 and TKMK00 decompression in C. Far fewer changes to the game than in the Super Mario 64 port, which removes the segments |
| One step per frame | the console's threads are gone: one start, one step per frame told how many vertical blanks went by, which is how the game keeps its speed when a frame is slow |
| Renderer | the one of the Super Mario 64 port, plus what this game needs: the early F3DEX quadrangle command, pictures drawn in strips, textures of any size, a general colour combiner (the inherited one knew a fixed set of formulas), intensity textures with alpha |
| First runs on the board | it started at the first try. Colours were noise (the app declared one byte order to the display and wrote the other): fixed. A race ran at 1.3 frames a second because of SD card reads: fixed with a block cache, 3.3 to 4.1 now |

## What is left

| Item | Notes |
|:---|:---|
| Super Mario 64: more drawn frames | about 6 a second at 320x240. Either a deeper rewrite of the pixel loops (long, uncertain) or a smaller render size, which is measured: 7.5 at 240x180, 10.5 at 160x120. A render-size choice in the game's menu does not exist yet (the size is a build constant) |
| Super Mario 64: level loads during play (castle door, paintings) | not tried: the board's timed keys cannot walk there. Bob-omb Battlefield was entered through the game's own stage list (a file switch, `levelselect` next to the pack, for measurements only) |
| Super Mario 64: sound by ear | built and measured, never listened to at a normal volume |
| Super Mario 64: a percentage while a level loads | the screen stands still for 1 to 1.5 s; the SD app copy and Mario Kart 64's course load show one |
| Mario Kart 64: speed in a race | 3 to 4 frames a second, all of it drawing, on one core. The banded two-core drawing of the Super Mario 64 port is not brought over yet; a smaller render size is not tried yet |
| Mario Kart 64: menu pictures | the portraits on player select and the course previews are wrong, on the PC too |
| Mario Kart 64: the rest of the game | the other 18 courses, split screen, battle, the ceremony: two courses have been seen so far |
| Mario Kart 64: sound | same engine family as Super Mario 64's; not started (the game's sound requests only queue up) |

## In the launcher

Decided by the user on 2026-10-05, after playing it: Super Mario 64 gets a place
on the current board, in a **Nintendo 64** section of the launcher, as it is
now (320x240, no sound), to be improved afterwards. An earlier decision the same
day had been to wait for the 32 MB module; this replaces it for Super Mario 64.

- The launcher tab "Nintendo 64" lists the files `*.sm64` and `*.mk64` in
  `/sd/roms/n64`. An empty file there, for example `Super Mario 64.sm64`, starts
  the game; its assets are the pack `/sd/retro-go/sm64/sm64.seg`
  (`/sd/retro-go/mk64/mk64.seg` for `<name>.mk64`), which must come from the
  same build as the app.
- The two apps are not built by `rg_tool.py` like the others, because their
  data comes from the user's ROMs and stays out of git:
  `retro-go/sm64-go/build_esp32.sh <baserom.us.z64>` and
  `retro-go/mk64-go/build_esp32.sh <mk64.us.z64>` build them and leave
  `<app>/build/<app>.bin`, which the image build then takes as it is.

### One partition for the Nintendo 64 games, and apps started from the SD card

Asked by the user on 2026-10-06; **flashed and checked on the board the same
day** (arcade, every app, the saves).

An ESP32 program runs from the flash, not from the card. But a program can be
kept on the card as a file and copied into a partition when it is started, and
several programs can then take turns in one partition:

- `n64app`, 1792 KB, is shared by Super Mario 64 and Mario Kart 64. Their
  programs are `/sd/retro-go/apps/sm64-go.bin` and `mk64-go.bin`. Starting the
  one that is not in the partition copies it there first, with a percentage on
  the screen: 8 s for Mario Kart 64, 10 s for Super Mario 64. Starting the one
  that is already there costs nothing. A new build of either game is installed
  by replacing its file on the card.
- `sdapp`, 640 KB, works the same way and holds OutRun.
- The launcher chooses the partition itself: the one that already holds that
  build, else the smallest one the file fits. No app is named in it.
- The room this gave back (Mario Kart 64 had a partition of 1344 KB for a
  day) went, at the user's choice, to Wolfenstein 3D and OpenTyrian, which have
  their own partitions again and start at once.

| Partition | Offset | Size |
|:---|:---|:---|
| launcher | 0x010000 | 1152 KB |
| retro-core | 0x130000 | 1216 KB |
| prboom-go | 0x260000 | 832 KB |
| gwenesis | 0x330000 | 1024 KB |
| n64app (Super Mario 64 or Mario Kart 64) | 0x430000 | 1792 KB |
| retro-extra | 0x5f0000 | 1280 KB |
| mame-go | 0x730000 | 2048 KB |
| wolf3d-go | 0x930000 | 640 KB |
| opentyrian-go | 0x9d0000 | 704 KB |
| gbsp | 0xa80000 | 832 KB |
| sdapp (OutRun) | 0xb50000 | 640 KB |
| mamerom (arcade game cache) | 0xbf0000 | 4096 KB |

The last 64 KB of the flash are left free on purpose: the image ends with a
256-byte footer, and `rg_tool.py` refuses an image larger than the flash.

### Duke Nukem 3D and Quake, set aside

The 16 MB flash was full (64 KB free), so the room came from two apps the user
chose: Duke Nukem 3D (1 MB) and Quake (0.75 MB), exactly the 1.75 MB of the
partition that is now `n64app`. The arcade game cache (`mamerom`, 4 MB) and every other app are
untouched and at the same addresses as before.

Nothing of the two was deleted:

- their sources are still in the fork (`retro-go/duke3d-go`, `retro-go/quake-go`)
  and still build: `python rg_tool.py --target=esp32-emu-turbo build duke3d-go`;
- their launcher tabs and art are still in the launcher; a tab shows only when
  its partition exists, so they are hidden, not removed;
- their game files on the SD card (`/sd/roms/duke3d`, `/sd/roms/quake`) and
  their saves are not touched.

To put them back: in `retro-go/rg_tool.py` restore the two commented lines in
`PROJECT_APPS`, add the two names to `DEFAULT_APPS`, find 1.75 MB (another
app set aside, or the 32 MB module), build the image and flash
it. That is a full flash write, like this change was.
