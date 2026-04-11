---
id: snes-optimization
title: SNES Optimization
sidebar_position: 4
---

# SNES Optimization

Progressive optimization plan to reach 60 FPS stable on SNES titles. Three software phases (assembly DSP, dual-core architecture, PPU rendering) plus a v2 hardware audio coprocessor option.

---

## Phase 4 — SNES Optimization (60 FPS target)

Progressive optimization of the snes9x core (Snes9x 2005 via Retro-Go) in 3 sub-phases over ~14 days. Target: **60 FPS stable** on standard titles (Super Mario World, Zelda ALttP, Chrono Trigger, Final Fantasy VI, Mega Man X). Baseline: ~30 FPS. See below for full technical details.

| Sub-phase | Step | Optimization | Days | Gain | Cumulative FPS |
|:---|:---|:---|---:|:---|:---|
| **4.1 — ASM DSP** | 4.1.1 | BRR Decode assembly (Xtensa LX7) | 1 | +5–7% | 30 → 32–33 |
| | 4.1.2 | Gaussian Interpolation assembly | 0.5 | +3–4% | 33 → 34–35 |
| | 4.1.3 | Voice Mixing assembly (fast-path) | 2 | +5–8% | 35 → 38–40 |
| | 4.1.4 | Echo FIR Filter assembly (8-tap unrolled) | 0.5 | +2–3% | 40 → 41–42 |
| **4.2 — Architecture** | 4.2.1 | Dual-Core SPC700 (Core 1 dedicated audio) | 2–3 | +35–45% | 42 → 50–52 |
| | 4.2.2 | Memory Layout (PSRAM → SRAM, ~100 KB) | 1 | +15–20% | 52 → 54–56 |
| | 4.2.3 | Overclock to 260 MHz | 0.01 | +8% | 56 → 57–58 |
| | 4.2.4 | Audio sample rate 32 → 16 kHz | 0.05 | +2–3% | 57–58 |
| **4.3 — PPU & Display** | 4.3.1 | PPU Fast-Path rendering (Mode 1) | 3–4 | +5–8% | 58 → 59–60 |
| | 4.3.2 | Tile Cache in SRAM (dirty-flag) | 1 | +3–5% | 60 + headroom |
| | 4.3.3 | DMA Display Push (double-buffer) | 1 | +2–3% | 60 + headroom |
| | 4.3.4 | Adaptive Frameskip (safety net) | 0.5 | safety net | **60 stable** |

---

## Why SNES is Hard on ESP32-S3

The SNES has three CPU-intensive subsystems that must be emulated in real-time:

```
Frame time budget: 16.67 ms (for 60 fps)

┌────────────────────────────────────────────┐
│ 65C816 CPU emulation         ~4.5 ms  27%  │
│ PPU rendering (2 BG layers)  ~5.0 ms  30%  │
│ SPC700 audio DSP             ~8.0 ms  48%  │  ← bottleneck
│ Display transfer             ~1.5 ms   9%  │
├────────────────────────────────────────────┤
│ TOTAL                       ~19.0 ms 114%  │  ← over budget
└────────────────────────────────────────────┘
```

At 114% of the frame budget on a single core, SNES emulation via Retro-Go (Snes9x 2005) currently reaches ~30 FPS on a target of 60 FPS. The 3-phase optimization plan below combines assembly-level DSP work, architectural changes (dual-core, memory layout), and rendering optimizations (PPU fast-path, tile cache, DMA display) to reach 60 FPS stable.

:::note
Performance gains are not perfectly additive — each optimization reduces the total frame time, so subsequent ones operate on a smaller base. The estimates account for this non-linearity.
:::

---

### Phase 4.1 — Assembly DSP (Xtensa LX7)

**Goal:** Rewrite the 4 heaviest S-DSP audio functions in native Xtensa assembly. These consume ~50% of the total SPC700 audio emulation time. ~120 lines of ASM, ~4 days.

#### 4.1.1 — BRR Decode (`DecodeBlockAsm`)

| | |
|:---|:---|
| **C function** | `DecodeBlock()` in soundux.cpp |
| **What it does** | Decodes BRR blocks (9 bytes → 16 PCM 16-bit samples). Native compressed format for all SNES audio samples. |
| **Call frequency** | ~2000–4000 times/frame (8 voices x sample rate x variable pitch) |
| **C bottleneck** | Loop with branches for clamping, stack spill for filter variables, unoptimized buffer access |
| **ASM optimization** | Zero-overhead `LOOP`, branchless `MIN`/`MAX` clamping, dedicated registers for filter state (a7/a8), load/compute interleaving |
| **Expected gain** | **+5–7%** on total frame time |
| **Effort** | ~30 lines ASM — 1 day |

Each BRR block has a header byte (shift amount + filter type 0–3) followed by 8 bytes of compressed data. Filters apply linear prediction using the 2 previous samples. The assembly eliminates branches in [-32768, +32767] clamping via native Xtensa `MIN`/`MAX` instructions, keeping old/older samples in registers a7/a8 without touching the stack.

#### 4.1.2 — Gaussian Interpolation (`GaussianInterpAsm`)

| | |
|:---|:---|
| **C function** | Inline interpolation in MixStereo/MixMono loop |
| **What it does** | 4-point filter with 512-entry Gaussian lookup table. Interpolates between decoded samples for resampling at desired pitch. |
| **Call frequency** | 32000/sec x 8 voices = 256,000 calls/sec |
| **C bottleneck** | 4 loads from gauss table + 4 multiplications + accumulate. Compiler generates ~18 instructions with intermediate load/stores. |
| **ASM optimization** | Gauss table in IRAM (`.section .iram1`), 4x `MULL`+`ADD` pipeline-scheduled, result in 8 net instructions. All 4 samples and 4 coefficients live in registers. |
| **Expected gain** | **+3–4%** on total frame time |
| **Effort** | ~10 lines ASM — half day |

The key is placing the Gaussian table (1 KB) in IRAM with `.section .iram1` — this eliminates PSRAM latency for every lookup. With coefficients pre-loaded in registers, the computation reduces to 4 `MULL` + 3 `ADD` + 1 `SRAI`. The C compiler typically cannot keep everything in registers because it has no aliasing guarantees on the pointers.

#### 4.1.3 — Voice Mixing (`MixVoiceAsm`)

| | |
|:---|:---|
| **C function** | `MixStereo()` / `MixMono()` in soundux.cpp |
| **What it does** | For each voice: applies ADSR/GAIN envelope, multiplies by L/R volume, accumulates into mix buffer. Handles pitch modulation, noise, and echo enable. |
| **Call frequency** | 1 per output sample x 8 voices = core loop of the entire DSP |
| **C bottleneck** | Most complex loop: per-voice branching (envelope state machine, pitch mod check, noise check, echo check), volume multiplications, stereo accumulate. Many variables, heavy register pressure. |
| **ASM optimization** | Fast-path for the common case (no pitch mod, no noise): eliminates branches, unrolls 8 voices, optimized stereo volume MAC. Fallback to C for special cases. |
| **Expected gain** | **+5–8%** on total frame time |
| **Effort** | ~60 lines ASM — 2 days (most complex) |

The strategy is a fast-path for the most frequent case (active voice, envelope in SUSTAIN state, no pitch modulation, no noise). This covers ~80% of real gameplay situations. For edge cases (ATTACK/DECAY/RELEASE, active pitch mod, noise generator), it falls back to the original C function. The fast-path uses Xtensa register windowing to keep all 8 volumes (L+R) and 8 envelopes in registers.

#### 4.1.4 — Echo FIR Filter (`EchoFIRAsm`)

| | |
|:---|:---|
| **C function** | Echo processing in main MixStereo loop |
| **What it does** | 8-tap FIR (Finite Impulse Response) on echo buffer. Each echo output sample = sum of 8 previous samples x 8 programmable coefficients. |
| **Call frequency** | 32000/sec (one per output sample, stereo) |
| **C bottleneck** | 8-iteration loop with signed multiplication and accumulate. Compiler doesn't fully unroll and doesn't optimally schedule the `MULL`. |
| **ASM optimization** | Full 8x unroll, `MULL` pipeline-scheduled with next sample load in parallel. Echo buffer pointer in register. Branchless clamping. |
| **Expected gain** | **+2–3%** on total frame time |
| **Effort** | ~20 lines ASM — half day |

With 8 taps fully unrolled, each `MULL` is scheduled while the next sample load is in flight, hiding memory latency. The 8 FIR coefficients (signed bytes) are loaded into two 32-bit registers (4 coefficients per register) and extracted with shift+mask, avoiding 8 separate loads.

#### Phase 4.1 Summary

| Function | ASM lines | Days | Gain % | FPS impact |
|:---|---:|---:|:---|:---|
| DecodeBlockAsm | ~30 | 1 | +5–7% | 30 → 32–33 |
| GaussianInterpAsm | ~10 | 0.5 | +3–4% | 33 → 34–35 |
| MixVoiceAsm | ~60 | 2 | +5–8% | 35 → 38–40 |
| EchoFIRAsm | ~20 | 0.5 | +2–3% | 40 → 41–42 |
| **TOTAL Phase 4.1** | **~120** | **4** | **+15–22%** | **30 → 38–42 FPS** |

---

### Phase 4.2 — Architectural Optimization

**Goal:** Restructure the emulator to leverage the ESP32-S3 dual-core and optimize memory layout. This phase has the single biggest impact overall. ~4 days.

#### 4.2.1 — Dual-Core SPC700 Separation

| | |
|:---|:---|
| **Intervention** | Move the entire SPC700 + DSP emulation (now ASM-optimized from Phase 4.1) to a dedicated FreeRTOS task on Core 1. |
| **Current state** | CPU 65C816, PPU, and SPC700 all run on Core 0 sequentially. Core 1 is fully idle — Wi-Fi and Bluetooth are not enabled in `sdkconfig.defaults` for Phase 1 hardware validation, so there is no WiFi/BT stack consuming Core 1. Future revisions that enable Wi-Fi will need to reserve Core 1 budget. |
| **Target architecture** | **Core 0:** CPU 65C816 + PPU + game logic. **Core 1:** SPC700 CPU + DSP (Phase 4.1 assembly) + I2S output via DMA. Communication via 4 lock-free I/O ports (atomic read/write). |
| **Implementation** | FreeRTOS task pinned to Core 1 with high priority. DMA-capable ring buffer (`MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL`) between DSP and I2S driver. The 4 SPC ↔ CPU ports are atomic variables (no mutex needed). |
| **Risks** | Temporal synchronization: some games depend on exact timing between CPU and SPC700. **Solution:** timestamp-based sync with ±64 sample tolerance (~2ms). Works for 95%+ of games. |
| **Expected gain** | **+35–45%** on total frame time |
| **Effort** | 2–3 days |

This is the single most impactful change in the entire plan. Freeing Core 0 from all audio emulation virtually doubles the available CPU budget for CPU+PPU.

```
Core 0 (main):                 Core 1 (audio):
  65C816 CPU emulation           SPC700 CPU emulation
  PPU rendering                  DSP (assembly from Phase 4.1)
  Display transfer               I2S DMA output feed
  Input polling

  ~10.5 ms/frame                 ~8.0 ms/frame → ~5 ms with ASM
  → bottleneck at 11ms           (runs fully in parallel)
```

#### 4.2.2 — Memory Layout Optimization

| | |
|:---|:---|
| **Intervention** | Relocate critical data structures from PSRAM to internal SRAM (512 KB). |
| **Structures to move** | SPC700 RAM (64 KB), PPU tile cache (~32 KB), palette RAM (512 B), OAM sprite table (544 B), CGRAM (512 B), DSP registers (128 B). **Total: ~100 KB in SRAM.** |
| **Impact** | Octal PSRAM has ~80–120ns random access latency vs ~10ns for internal SRAM. The DSP and PPU make thousands of random accesses per frame. **8–10x latency difference.** |
| **Implementation** | Replace `malloc()` with `heap_caps_malloc(size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)` for identified structures. Verify remaining SRAM budget with `heap_caps_get_free_size()`. |
| **Expected gain** | **+15–20%** on total frame time |
| **Effort** | 1 day (few lines of code, but requires profiling) |

#### 4.2.3 — Overclock to 260 MHz

| | |
|:---|:---|
| **Intervention** | Increase clock from 240 to 260 MHz via ESP-IDF menuconfig (unofficial but stable). |
| **Implementation** | In sdkconfig: `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ=260`. Or runtime: `esp_pm_configure()` with `max_freq_mhz=260`. |
| **Risks** | Minimal. The S3 is officially tested to 240 MHz, but 260 MHz is widely used in the community without stability issues. No significant power consumption increase. |
| **Expected gain** | **+8%** linear across everything |
| **Effort** | 10 minutes |

#### 4.2.4 — Audio Sample Rate Reduction

| | |
|:---|:---|
| **Intervention** | Reduce DSP sample rate from 32 kHz to 16 kHz. Halves the number of samples to compute per second. |
| **Audio impact** | Slightly lower perceived quality on high frequencies (cymbals, hi-hat). For most SNES music the difference is minimal on a handheld speaker. |
| **Expected gain** | **+5–8%** on audio processing (~2–3% total after dual-core) |
| **Effort** | 30 minutes |

#### Phase 4.2 Summary

| Intervention | Days | Gain % | Cumulative FPS |
|:---|---:|:---|:---|
| Dual-Core SPC700 | 2–3 | +35–45% | 42 → 50–52 |
| Memory Layout SRAM | 1 | +15–20% | 52 → 54–56 |
| Overclock 260 MHz | 0.01 | +8% | 56 → 57–58 |
| Sample Rate 16 kHz | 0.05 | +2–3% | 57–58 |
| **TOTAL Phase 4.2** | **~4** | **cumulative** | **42 → 56–58 FPS** |

---

### Phase 4.3 — The Last Mile: PPU & Display

**Goal:** Go from ~57 to 60 FPS stable by optimizing PPU rendering and the display pipeline. More complex optimizations but necessary for the final 5%. ~6 days.

#### 4.3.1 — PPU Fast-Path Rendering

| | |
|:---|:---|
| **Intervention** | Create optimized paths for common PPU cases: Mode 1 (used by 70%+ of games), no clipping windows, no mosaic, no complex color math. |
| **Detail** | The Snes9x 2005 PPU handles ALL cases (Mode 0–7, windows, mosaic, color math, hi-res, interlace, offset-per-tile) in a single generic code path with many branches. The fast-path eliminates checks for features not used in the current scanline. |
| **Expected gain** | **+5–8%** on total frame time |
| **Effort** | 3–4 days (requires deep PPU understanding) |

#### 4.3.2 — Tile Cache in SRAM

| | |
|:---|:---|
| **Intervention** | Cache decoded tiles in internal SRAM. The PPU decodes the same tiles hundreds of times per frame (repeated background tiles). With dirty-flag tracking, only re-decode when VRAM changes. |
| **Expected gain** | **+3–5%** |
| **Effort** | 1 day |

#### 4.3.3 — DMA Display Push

| | |
|:---|:---|
| **Intervention** | Use the ESP32-S3 DMA to transfer the framebuffer to the display (8-bit 8080 parallel) without engaging the CPU. Double-buffering: while DMA sends frame N, the CPU renders frame N+1. |
| **Expected gain** | **+2–3%** |
| **Effort** | 1 day |

#### 4.3.4 — Adaptive Frameskip (Safety Net)

| | |
|:---|:---|
| **Intervention** | If the frame budget (16.67ms) is exceeded, skip rendering the next frame (but still execute game logic). Frameskip 1 = 30 FPS perceived but gameplay at 60. |
| **Strategy** | Auto-adaptive: measure previous frame time. If over 16.67ms, skip render. If under 15ms, never skip. Zone 15–16.67ms: skip 1 every 4 frames. **Perceived result: 45–60 FPS constant.** |
| **Expected gain** | Safety net — maintains 60 perceived FPS even at ~55 real FPS |
| **Effort** | Half day |

---

### Complete FPS Progression

| # | Intervention | FPS pre | FPS post | Delta FPS | Days cum. |
|:---|:---|---:|---:|:---|---:|
| F4.1 | BRR Decode ASM | 30 | 32–33 | +2–3 | 1 |
| F4.1 | Gaussian Interp ASM | 33 | 34–35 | +1–2 | 1.5 |
| F4.1 | Voice Mixing ASM | 35 | 38–40 | +3–5 | 3.5 |
| F4.1 | Echo FIR ASM | 40 | 41–42 | +1–2 | 4 |
| F4.2 | Dual-Core SPC700 | 42 | 50–52 | **+8–10** | 7 |
| F4.2 | Memory Layout SRAM | 52 | 54–56 | +2–4 | 8 |
| F4.2 | Overclock 260 MHz | 56 | 57–58 | +1–2 | 8 |
| F4.2 | Sample Rate 16 kHz | 58 | 58 | +0–1 | 8 |
| F4.3 | PPU Fast-Path | 58 | 59–60 | +1–2 | 12 |
| F4.3 | Tile Cache SRAM | 60 | 60 | +headroom | 13 |
| F4.3 | DMA Display | 60 | 60 | +headroom | 14 |
| F4.3 | Adaptive Frameskip | — | **60 stable** | safety net | 14.5 |

---

### Game Compatibility

| Game | Complexity | Expected FPS | Playable? |
|:---|:---|:---|:---|
| Super Mario World | Low | 60 | **Yes** |
| Zelda: A Link to the Past | Low | 58–60 | **Yes** |
| Chrono Trigger | Medium | 55–60 | **Yes** |
| Final Fantasy VI | Medium | 55–60 | **Yes** |
| Mega Man X | Medium | 55–58 | **Yes** |
| Super Metroid | Medium-High | 50–58 | **Yes*** |
| Donkey Kong Country | High | 45–55 | Partial |
| Street Fighter II Turbo | High | 45–55 | Partial |
| Star Fox (Super FX) | Extreme | 20–30 | **No** |
| Yoshi's Island (Super FX 2) | Extreme | 15–25 | **No** |

\* With occasional adaptive frameskip in heavy scenes.

:::note Games with special coprocessors
Games using special coprocessors (Super FX, Super FX 2, SA-1, DSP-1/2/3/4) would require an ESP32-P4 (400 MHz) or better to reach full speed. These chips add a significant computation overhead that cannot be optimized away on the ESP32-S3.
:::

:::tip SNES on v2 (ESP32-P4)
The ESP32-P4 at 400MHz with 2.1x the CoreMark score would bring SNES to full-speed with full audio quality for virtually all standard games, and make Super FX titles partially playable.
:::

### Audio Profiles

The SPC700 audio DSP is the single biggest CPU bottleneck before Phase 4.1 assembly optimizations. Three selectable profiles trade audio quality for frame rate, toggled in-game via **Menu button → Audio: Full / Fast / OFF**.

#### Profile Comparison

| Profile | Sample rate | Interpolation | Echo/Reverb | Channels | DSP time (pre-ASM) | DSP time (post-ASM) |
|:---|:---|:---|:---|:---|---:|---:|
| **Full** | 32 kHz | Gaussian (4-tap) | Yes | Stereo | ~8.0 ms | ~5.0 ms |
| **Fast** | 16 kHz | Linear (2-tap) | No | Mono | ~2.5 ms | ~1.5 ms |
| **OFF** | — | — | — | — | 0 ms | 0 ms |

After Phase 4.1 (ASM DSP) + Phase 4.2 (dual-core), audio runs on Core 1 in parallel. With all optimizations applied, Full audio profile at 60 FPS is the target — no quality compromise needed for standard games.

:::tip Recommended: Full audio after all optimizations
Unlike the pre-optimization estimates, the 3-phase plan targets **60 FPS with full 32kHz stereo audio** for standard games (Super Mario World, Zelda, Chrono Trigger, FF6). Audio Fast/OFF remain available as fallback options for heavy scenes or complex games.
:::

---

### Phase 5 — v2 Hardware Audio Coprocessor

**Goal:** Add an **ESP32-S3-MINI-1** module as a dedicated audio coprocessor on the v2 PCB. This completely offloads audio processing from the ESP32-S3 for **all emulators** — not just SNES. Both ESP32-S3 cores become 100% available for CPU + PPU + game logic. **~5 days** (down from 14 with RP2040 — see [Why ESP32-S3-MINI-1 instead of RP2040](#why-esp32-s3-mini-1-instead-of-rp2040) for the rationale).

#### Why a Hardware Audio Coprocessor?

Even after Phase 4 optimizations, the ESP32-S3 spends one entire core on SNES audio (SPC700 + DSP). For simpler emulators (NES, GB, Genesis), audio still consumes I2S DMA time and interrupt cycles. A dedicated audio chip eliminates this entirely.

```
v1 Architecture (software only):
┌──────────────────────────────────────────────────────┐
│ ESP32-S3                                             │
│   Core 0: CPU + PPU + Display                        │
│   Core 1: SPC700 + DSP + I2S DMA ← audio burden     │
│                                        │             │
│                                   I2S bus            │
│                                        │             │
│                                   PAM8403 → Speaker  │
└──────────────────────────────────────────────────────┘

v2 Architecture (ESP32-S3-MINI-1 audio hub):
┌──────────────────────┐   SPI 10MHz    ┌──────────────────────┐
│ ESP32-S3 (main)      │ ──────────────→│ ESP32-S3-MINI-1      │
│   Core 0: CPU + PPU  │   commands     │   Core 0: SPC700 DSP │
│   Core 1: CPU + PPU  │   + PCM data   │   Core 1: I2S output │
│   (both 100% free    │               │                      │
│    for emulation)    │               │     I2S (hardware)   │
└──────────────────────┘               │          │           │
                                       │     PAM8403          │
                                       │          │           │
                                       │      Speaker         │
                                       └──────────────────────┘
```

#### Why ESP32-S3-MINI-1 instead of RP2040

The original Phase 5 design used an RP2040 (ARM Cortex-M0+, $0.70). After analysis, the **ESP32-S3-MINI-1** is the better choice despite a higher module cost (~$3.25), because the development time savings and architectural simplification far outweigh the $2.26 BOM increase.

##### Development time comparison

| Step | Task | RP2040 | ESP32-S3-MINI-1 | Savings |
|:---|:---|---:|---:|:---|
| 5.1 | Circuit design + PCB | 2 days | **1 day** | Module integrates crystal + flash |
| 5.2 | SPI protocol | 2 days | **1 day** | Same ESP-IDF SPI API on both sides |
| 5.3 | Passthrough firmware (PCM relay) | 1 day | **0.5 days** | Copy `audio.c` I2S code, same API |
| 5.4 | SPC700 native firmware | 5 days | **0.5 days** | Xtensa ASM from Phase 4.1 runs **identically** |
| 5.5 | ESP32 firmware integration | 2 days | **1 day** | Single `idf.py`, one build system |
| 5.6 | Testing + latency tuning | 2 days | **1 day** | Same `idf.py monitor`, same log format |
| **Total** | | **14 days** | **~5 days** | **-9 days (64% reduction)** |

The decisive factor is **Step 5.4**: with the RP2040, you must rewrite ~120 lines of Xtensa LX7 assembly (BRR decode, Gaussian interpolation, voice mixing, echo FIR from Phase 4.1) into ARM Thumb assembly — a complete cross-architecture port requiring testing, debugging, and re-optimization. With the ESP32-S3-MINI-1, you copy the `.S` files and compile. Done.

##### Technical advantages

| Aspect | RP2040 | ESP32-S3-MINI-1 | Winner |
|:---|:---|:---|:---|
| **Architecture** | ARM Cortex-M0+ | Xtensa LX7 (same as main chip) | MINI-1 |
| **Clock speed** | 133 MHz | 240 MHz (+80%) | MINI-1 |
| **Internal SRAM** | 264 KB | 512 KB (+94%) | MINI-1 |
| **I2S** | Via PIO (custom bitbang) | Native hardware I2S | MINI-1 |
| **SPI slave** | Hardware | Hardware (same ESP-IDF API) | Tie |
| **Toolchain** | Pico SDK (separate) | ESP-IDF (same as main) | MINI-1 |
| **ASM compatibility** | Zero (must rewrite all) | 100% (identical Xtensa LX7) | MINI-1 |
| **External components** | Crystal + flash + 4 caps | None (all integrated) | MINI-1 |
| **WiFi/BT** | No | Yes (future upgrade path) | MINI-1 |
| **Unit cost** | $0.70 + $0.29 external = $0.99 | $3.25 + $0.02 caps = $3.27 | RP2040 |
| **Development time** | 14 days | 5 days | MINI-1 |

##### Key architectural benefits

1. **One toolchain** — No need to install Pico SDK, learn RP2040 PIO, or maintain two build systems in Docker. The entire project stays pure ESP-IDF.

2. **Unified debugging** — Both chips flash and monitor via `idf.py`. Same serial log format, same profiling APIs, same Docker Compose target (just a different `idf.py` target for the coprocessor).

3. **Simpler BOM** — Eliminates the 12 MHz crystal, W25Q16 flash chip, and 4 extra decoupling capacitors. The module has everything integrated.

4. **Faster CPU** — 240 MHz vs 133 MHz with higher IPC (Xtensa LX7 is a more capable core than Cortex-M0+). The SPC700 emulation runs with massive headroom.

5. **More SRAM** — 512 KB vs 264 KB. The SPC700 needs 64 KB RAM + DSP buffers + I2S ring buffer. On the MINI-1, there is 400+ KB free for audio mixing buffers and future features.

6. **Future upgrade path** — The ESP32-S3-MINI-1 has WiFi and Bluetooth 5.0 LE built in. Future firmware could enable WiFi ROM downloads, Bluetooth wireless controllers, or OTA updates for the coprocessor — all with zero hardware changes.

#### ESP32-S3-MINI-1 Specifications

| Parameter | Value |
|:---|:---|
| **Module** | ESP32-S3-MINI-1-N8 (Espressif) |
| **SoC** | ESP32-S3 (Xtensa LX7 dual-core) |
| **Cores** | 2x Xtensa LX7 @ 240 MHz |
| **Internal SRAM** | 512 KB |
| **Flash** | 8 MB Quad SPI (integrated) |
| **PSRAM** | None (not needed for audio) |
| **I2S** | 2x hardware I2S (8/16/24/32-bit) |
| **SPI** | SPI2 + SPI3 (general-purpose, DMA-capable) |
| **GPIOs** | 39 (including 4 strapping) |
| **Antenna** | On-board PCB antenna |
| **Operating voltage** | 3.0–3.6V |
| **Power** | ~50 mA active (single core audio task) |
| **Dimensions** | 15.4 × 20.5 × 2.4 mm |
| **LCSC Part #** | C2913206 |
| **Unit cost** | ~$3.25 |

:::note Why N8 (no PSRAM) instead of N4R2?
The audio coprocessor only needs internal SRAM. SPC700 RAM is 64 KB, DSP buffers ~32 KB, I2S ring buffer ~16 KB — total ~112 KB, well within the 512 KB internal SRAM. PSRAM would add latency to the audio path without benefit. The N8 variant also keeps all 39 GPIOs available (N4R2 loses GPIO26 to PSRAM).
:::

#### Dual-Mode Firmware

The ESP32-S3-MINI-1 runs two firmware modes, selected by the main ESP32-S3 via an SPI command at emulator launch:

| Mode | Active for | MINI-1 Core 0 | MINI-1 Core 1 | Audio latency |
|:---|:---|:---|:---|---:|
| **Passthrough** | NES, GB, GBC, SMS, GG, PCE, Genesis, Lynx | Receive PCM via SPI → ring buffer | Ring buffer → I2S DMA output | under 2 ms |
| **SPC700 Native** | SNES | Full SPC700 CPU + S-DSP emulation (Phase 4.1 ASM) | I2S DMA output from DSP buffer | under 5 ms |

**Passthrough mode:** The main ESP32-S3 computes audio samples as usual (e.g., NES APU, GB sound) and sends raw PCM over SPI. The MINI-1 relays them to I2S via DMA. This frees the main ESP32-S3 from I2S DMA interrupts and buffer management. The MINI-1 firmware reuses the same `i2s_std` driver code from Phase 1 (`audio.c`).

**SPC700 Native mode:** The main ESP32-S3 sends SPC700 I/O port writes (4 bytes) and timing sync packets over SPI. The MINI-1 runs the complete SPC700 CPU emulation + S-DSP natively. The Phase 4.1 Xtensa assembly functions (`DecodeBlockAsm`, `GaussianInterpAsm`, `MixVoiceAsm`, `EchoFIRAsm`) run **identically** — same opcodes, same register layout, same instruction timings. At 240 MHz with 512 KB SRAM, the MINI-1 has massive headroom for real-time SPC700 emulation.

#### SPI Communication Protocol

| Command | Direction | Payload | Rate |
|:---|:---|:---|:---|
| `MODE_SET` | Main → MINI-1 | 1 byte (0=Passthrough, 1=SPC700) | At emulator launch |
| `PCM_DATA` | Main → MINI-1 | 256–512 bytes PCM (16-bit stereo) | 32 kHz / buffer size |
| `SPC_PORT_WRITE` | Main → MINI-1 | 4 bytes (ports 0-3) | Per CPU write (~1000/frame) |
| `SPC_SYNC` | Main → MINI-1 | 4 bytes (timestamp) | Every 2 ms |
| `SPC_UPLOAD` | Main → MINI-1 | Variable (SPC700 program) | At game load |
| `STATUS` | MINI-1 → Main | 4 bytes (ports 0-3 readback) | On request |

**SPI bus:** 10 MHz clock, Mode 0, 8-bit frames. Both sides use the same `spi_slave`/`spi_master` ESP-IDF driver with DMA. At 10 MHz (higher than the 4 MHz originally planned for RP2040, since both chips support ESP-IDF SPI DMA natively), a 512-byte PCM buffer transfers in ~0.4 ms.

#### BOM Impact (v1 → v2)

| Component | Qty | Unit cost | Total | Notes |
|:---|---:|---:|---:|:---|
| ESP32-S3-MINI-1-N8 | 1 | $3.25 | $3.25 | Audio coprocessor (flash + crystal integrated) |
| 100nF caps (decoupling) | 2 | $0.01 | $0.02 | Power filtering |
| 3.3V LDO (shared) | — | — | $0.00 | Uses existing AMS1117 |
| **Total v2 addition** | | | **$3.27** | |

**v2 total BOM delta:** ~$3.27. The ESP32-S3-MINI-1 runs at 3.3V from the existing AMS1117 regulator (which has 800 mA headroom — the MINI-1 adds ~50 mA for single-core audio tasks, well within budget).

**Comparison with RP2040 BOM:** The RP2040 approach cost $0.99 in parts (chip + flash + crystal + caps) but required 14 days of development. The MINI-1 costs $2.28 more per unit but saves 9 days. On a 5-unit JLCPCB order, that is $11.40 total — a trivial cost for 64% less development time. The simpler PCB layout (3 components vs 7) also reduces routing complexity.

#### GPIO / SPI Wiring

In v2, the main ESP32-S3's I2S pins (GPIO 15, 16, 17) are freed since audio output moves to the coprocessor. These pins are repurposed for the SPI link to the MINI-1:

```
ESP32-S3 Main (SPI Master)         ESP32-S3-MINI-1 (SPI Slave)
──────────────────────────         ─────────────────────────────
GPIO 15 (SPI_CLK)         ───────→ GPIO 12 (SPI2_CLK)
GPIO 16 (SPI_MOSI)        ───────→ GPIO 11 (SPI2_MOSI)
GPIO 17 (SPI_MISO)        ←─────── GPIO 13 (SPI2_MISO)
GPIO 20 (SPI_CS)           ───────→ GPIO 10 (SPI2_CS)

ESP32-S3-MINI-1 (I2S hardware)    Audio
─────────────────────────────      ─────
GPIO 15 (I2S_BCLK)        ───────→ PAM8403 BCLK
GPIO 16 (I2S_LRCLK)       ───────→ PAM8403 LRCLK
GPIO 17 (I2S_DOUT)         ───────→ PAM8403 DIN
```

**Notes:**
- The main ESP32-S3's I2S pins (GPIO 15–17) become SPI pins in v2 — clean reuse, no wasted GPIOs.
- GPIO 20 (USB_D+ in v1) serves as SPI chip select in v2. Native USB is no longer available in v2 (debug via SPI or UART instead).
- The MINI-1 uses its own GPIO 15–17 for I2S output to the PAM8403 — the same pin numbers as v1, making the audio output path identical.

#### Performance: v1 vs v2

| Metric | v1 (software) | v2 (ESP32-S3-MINI-1) | Improvement |
|:---|:---|:---|:---|
| **ESP32 cores for emulation** | 1.0–1.5 (Core 1 shared with audio) | 2.0 (both cores 100%) | +33–100% |
| **SNES audio CPU cost** | ~5 ms/frame (ASM, Core 1) | 0 ms (offloaded) | **-100%** |
| **NES/GB audio CPU cost** | ~0.5 ms/frame + I2S IRQ | 0 ms (offloaded) | **-100%** |
| **Audio latency** | 2–5 ms (DMA buffer) | 2–5 ms (SPI + DMA) | Same |
| **Audio quality** | 16 kHz (compromise for FPS) | 32 kHz stereo (no compromise) | **2x sample rate** |
| **Coprocessor clock** | — | 240 MHz (80% faster than RP2040) | N/A |
| **Power consumption** | ~180 mA (both cores loaded) | ~230 mA (+50 mA MINI-1) | +28% |
| **BOM cost** | $33 | $36.27 | +$3.27 |
| **Development time** | — | 5 days (vs 14 for RP2040) | **-64%** |

#### SNES FPS Impact (v2)

With the ESP32-S3-MINI-1 handling all audio, the main ESP32-S3 frame budget changes drastically:

```
v2 Frame time budget: 16.67 ms (for 60 fps)

┌────────────────────────────────────────────────┐
│ 65C816 CPU emulation         ~4.5 ms  27%      │
│ PPU rendering (2 BG layers)  ~5.0 ms  30%      │
│ SPC700 audio DSP              0.0 ms   0%      │ ← offloaded to MINI-1
│ Display transfer             ~1.5 ms   9%      │
├────────────────────────────────────────────────┤
│ TOTAL                       ~11.0 ms  66%      │ ← 34% headroom!
└────────────────────────────────────────────────┘
```

At only 66% of the frame budget **before any Phase 4 software optimizations**, v2 hardware reaches 60 FPS for standard SNES games out of the box. Phase 4 optimizations (PPU fast-path, tile cache, overclock) become headroom for complex games.

#### v2 Game Compatibility (All 16-bit Systems)

| System | Example games | v1 FPS | v2 FPS | Notes |
|:---|:---|---:|---:|:---|
| **NES** | Super Mario Bros, Zelda | 60 | 60 | Already full speed; v2 frees CPU headroom |
| **Game Boy** | Tetris, Pokemon | 60 | 60 | Already full speed |
| **GBC** | Pokemon Crystal | 60 | 60 | Already full speed |
| **SMS** | Sonic the Hedgehog | 60 | 60 | Already full speed |
| **Game Gear** | Sonic Triple Trouble | 60 | 60 | Already full speed |
| **PCE** | Bonk's Adventure | 60 | 60 | Already full speed |
| **Lynx** | California Games | 60 | 60 | Already full speed |
| **Genesis** | Sonic, Streets of Rage | 50–60 | **58–60** | +8–10 FPS from freed Core 1 |
| **SNES (standard)** | Mario World, Zelda ALttP | 30 | **55–60** | Audio offloaded, no Phase 4 needed |
| **SNES (complex)** | Chrono Trigger, FF6 | 25–30 | **50–58** | Phase 4 PPU optimizations for 60 |
| **SNES (Super FX)** | Star Fox, Yoshi's Island | 15–25 | **25–40** | Coprocessor still too heavy for 60 |

:::tip v2 makes Phase 4 optional for most SNES games
With the ESP32-S3-MINI-1 handling all audio natively (running the same Xtensa LX7 assembly from Phase 4.1), the biggest SNES bottleneck (48% of frame time) is eliminated at the hardware level. Standard SNES games reach 55–60 FPS **without any assembly or architectural optimization** on the main chip. Phase 4 becomes a bonus for pushing complex titles to a stable 60.
:::

#### v2 Implementation Roadmap (5 days)

| Step | Task | Days | Details |
|:---|:---|---:|:---|
| **5.1** | Circuit design + PCB | 1 | Add ESP32-S3-MINI-1-N8 footprint to KiCad. Only 2 decoupling caps needed (no crystal, no flash). Route 4 SPI traces + 3 I2S traces to PAM8403. Simpler than RP2040 (3 components vs 7). |
| **5.2** | SPI communication protocol | 1 | Use `spi_master` on main ESP32 and `spi_slave` on MINI-1 — both from ESP-IDF. Same API, same DMA engine. Protocol: `MODE_SET` + `PCM_DATA` + `SPC_PORT_WRITE`. Can start from ESP-IDF SPI slave example. |
| **5.3** | Passthrough firmware | 0.5 | Copy `audio.c` from Phase 1 to the coprocessor project. Replace `i2s_write()` source from local buffer to SPI-received buffer. Same `i2s_std` driver, same config, same sample format. |
| **5.4** | SPC700 native firmware | 0.5 | Copy Phase 4.1 assembly files (`.S`) + SPC700 C emulation code to coprocessor project. Compile with `idf.py set-target esp32s3 && idf.py build`. The Xtensa assembly runs identically — same opcodes (`MULL`, `MIN`, `MAX`, `LOOP`), same register layout, same instruction timing. No porting needed. |
| **5.5** | Main ESP32 integration | 1 | Replace I2S audio output in Retro-Go with SPI transmit to coprocessor. Add `MODE_SET` command at emulator launch. The emulator code doesn't change — only the audio output path switches from local I2S to SPI. |
| **5.6** | Testing + latency tuning | 1 | Same `idf.py monitor` for both chips. Same serial log format. Same profiling APIs (`esp_timer_get_time()`). Can test both chips simultaneously with two USB cables. |
