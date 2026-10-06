# Arcade roadmap checks, 2026-10-05 (play build c613bc47)

## Street Fighter II save states (open item 3)

Board, sf2ce from the CPS1 tab: `save 0` -> "CTL save done slot 0" (the
2026-10-03 failure, "save queued" with no "done", does not reproduce; the
state buffer is borrowed from the scroll-2 cache as designed). In-session
`load 0` and `resume` from the launcher both return to the saved boot-screen
scene and continue (webcam). 

2026-10-06, in a fight (Ryu vs Chun-Li, round 1): `save 0` -> "CTL save
done slot 0"; 12 s of play later (Ryu lost more health) `load 0` -> "CTL
load done slot 0" and the webcam shows the saved scene again: same
positions, same health bars, and the fight goes on. Leaving to the launcher
and `resume` from slot 0 also comes back into the fight and keeps playing.
SF2 save states in a fight: closed.

## Knights of the Round, 16-bit frames to the display (`cps1_indexed`)

40 s play window, coin + START x3, hold right with A/B:

| path | FPS avg / min | drawn/s | internal heap min |
|---|---|---|---|
| core path (default) | 43.3 / 40 | 14.5 | 20 KB |
| `cps1_indexed` (16-bit frames converted on core 1) | 41.5 / 36 | 13.9 | 13 KB |

Picture correct on both (webcam bursts). Slower and 7 KB less internal RAM:
the 16-bit hand-over stays off by default.

## Robby Roto resume (open item 6)

Fixed in the fork (a75d9c9f): the Astrocade video registers are saved
(mamego_extra_state). PC: the maze is back 30 frames after loading a state in
a new run (was 100 black frames). Board check pending.


## System 16 sprite flicker (introduced and fixed the same day)

d38ed380 (System 16 frames to the display) drew sprites only on every other
frame: sprite.c kept the screen bitmap's base from sprite_init(). Seen by the
user; webcam bursts confirmed (background only on alternate frames). Fixed in
c613bc47: sprite_draw() takes the current Machine->scrbitmap.

## Neo Geo 16-bit games: frames to the display (open item 4), fork 6781e2de

Metal Slug 2, KOF '95 and Shock Troopers are not raster games: they are
`GAME_REQUIRES_16BIT` (more than 256 colours a frame), so they cannot take the
8-bit band path. Their drawn frames were converted to RGB565 by core 1
(convert+display ~20 ms a frame in Metal Slug 2, core 1 at 90-96 %). The
display now reads the 16-bit pen bitmap and looks the colours up while it
scales (new surface format RG_PIXEL_PAL16_BE). Switch: `neo_noindexed16`.

40 s play window (FPS avg / min, drawn per second, internal heap min):

| game | converted on core 1 (before) | pens to the display (after) |
|---|---|---|
| Metal Slug 2 | 45.5 / 36, 15.2, 12 KB | 52.0 / 42, 17.3, 18 KB |
| Shock Troopers | - | 60.0 / 58, 27-28, 22 KB |
| KOF '95 | - | 54.9 / 47, 22.7, 22 KB |

Webcam bursts: picture correct on every frame, both paths.

## CPS1 16-bit games on the same path (fork ced95664, default)

Knights of the Round, same play window: 43.3 / 40 (core path) -> 47.5 / 42
(pens to the display), drawn 14.5 -> 15.9, internal heap 18 KB; picture
correct (webcam). Final Fight (8-bit, unchanged path) 54.6 / 50, 18.2 drawn.
`cps1_noindexed16` keeps the 16-bit games on core 0's path.

## CPS1: bottom scroll 3 drawn opaque (fork, after a6a3dc2e)

Scroll 3 is the bottom layer in almost every frame of play (PC: Final Fight
3599 of 3600, SF2 3594), so the visible area was cleared each drawn frame.
Now scroll 3 as bottom is drawn opaque with pen 15 mapped to the clear's pen;
only uncovered strips and empty cells are cleared. PC gate IDENTICAL on
ffight, sf2ce, ghouls, cawing, knights (4000 frames, play2).
Board, MAMEBENCH=4 MAMEPROF=1 Final Fight, core 0 video: 20.18 -> 19.70 ms a
frame; fillbitmap 15.7 % -> 7.9 % of samples (the opaque drawer takes part of
it back: it now writes every scroll-3 pixel). Play window: ffight 55.2 / 48,
18.4 drawn; ghouls 60.3, 51.5 drawn; sf2ce 43.2 (a fight scene, not
comparable with the morning's 50.2). Webcam bursts clean.
Discarded: priority bitmap cleared by rows (dbd44046): no measurable change.

## Dead buttons of 2026-10-03 (open item)

What is known: the one-off binary on the board that day ignored the gamepad.
The "stale bench flags" explanation was tested on the PC on 2026-10-03 and
not reproduced: a MAMEBENCH=0 build after a MAMEBENCH=2 build in the same
directory has no "MAMEBENCH frames" string and no -DMAMEBENCH (rg_tool.py
passes -D cache entries to idf.py, which re-runs CMake each time). The cause
of that one binary stays unexplained. What guards against it since then:
`board_install.sh` refuses any binary that contains "MAMEBENCH frames" (a
bench build ignores the pad) or that a failed build left behind.

2026-10-06, the play build now on the board, Aero Fighters (the game the
user reported): SELECT puts a coin in ("PRESS 1P or 2P BUTTON"), START opens
player select and the mission, the D-pad moves the plane (webcam). Input
works; nothing to fix without a new occurrence.
