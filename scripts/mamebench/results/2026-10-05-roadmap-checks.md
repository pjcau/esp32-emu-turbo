# Arcade roadmap checks, 2026-10-05 (play build c613bc47)

## Street Fighter II save states (open item 3)

Board, sf2ce from the CPS1 tab: `save 0` -> "CTL save done slot 0" (the
2026-10-03 failure, "save queued" with no "done", does not reproduce; the
state buffer is borrowed from the scroll-2 cache as designed). In-session
`load 0` and `resume` from the launcher both return to the saved boot-screen
scene and continue (webcam). Not yet repeated with a save taken in a fight.

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

## GG Aleste 3 black screen (open item 6)

Not an emulator defect. The "(Aleste Collection)" dump is M2's encrypted
build: a PC harness of smsplus shows the game resetting every ~5 frames; the
IRQ handler pointer at 0xC2F7 is cleared through the RAM mirror (0xE2F7) by a
loop entered at 0x404C, because the call to 0x4006 lands in bank 3 data. No
emulator runs this dump unpatched (Genesis Plus GX lists it as its one
exception); a patched ROM is needed.

## System 16 sprite flicker (introduced and fixed the same day)

d38ed380 (System 16 frames to the display) drew sprites only on every other
frame: sprite.c kept the screen bitmap's base from sprite_init(). Seen by the
user; webcam bursts confirmed (background only on alternate frames). Fixed in
c613bc47: sprite_draw() takes the current Machine->scrbitmap.
