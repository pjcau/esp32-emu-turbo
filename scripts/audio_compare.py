#!/usr/bin/env python3
"""audio_compare.py: can a listener tell two renderings of the same sound apart?

    scripts/audio_compare.py <reference.wav> <test.wav> [--same-frames | --align] [--seconds A-B] [--midpoint]

Made for the Arcade 60 fps plan's sound question: the chips rendered at 16 kHz
and doubled to the 32 kHz output (the firmware's AUDIO_MIX_HZ=16000) against
the chips rendered at 32 kHz. Works on the PC harness' dumps (`neoframes --wav`,
same scene, sample-aligned by construction) and on two microphone recordings of
the same scene (`--align` finds the offset from the loudness envelopes).

A 16 kHz file is first doubled exactly as the firmware does (each sample, and
between two of them a 12-tap interpolation; `--midpoint` gives the first
version, the plain midpoint), so the comparison is of what the speaker gets.
Any other rate (a 44.1 kHz dump, a microphone) is resampled to 32 kHz.
Comparing a 32 kHz dump with a 44.1 kHz one of the same frames gives the
difference between two renderings nobody would call different: the yardstick
for the 16 kHz one.
`--same-frames` is for two dumps of the same frames: the core emits a whole
number of samples a frame (533 at 32 kHz, 266 at 16), so the two files drift
apart by 0.1 s a minute and the test is stretched to the reference's length.
Waveforms are not subtracted: two correct renderings differ in phase, which
the ear does not hear. The comparison is of levels per frequency band over
time (32 ms frames, third-octave bands), which it does hear:

  - overall level difference;
  - per band: the long-term level difference, and over the frames where the
    reference has something in that band, the mean and the 95th percentile of
    the absolute difference;
  - how much of each file's energy lies above 8 kHz (what a 16 kHz rendering
    cannot contain, and what the doubling adds as images);
  - "extra" sound: frames where the test has clearly more in a band than the
    reference (aliasing shows here).

Rule of thumb used for the verdict: a level change in a band is noticeable from
about 1 dB when listened for, and a few dB in passing.
"""
import sys
import wave

import numpy as np

RATE = 32000
FRAME, HOP = 1024, 512
TAPS = np.array([-21, 73, -173, 359, -764, 2574, 2574, -764, 359, -173, 73, -21], dtype=np.float64)
MIDPOINT = False
EDGES = [89, 112, 141, 178, 224, 282, 355, 447, 562, 708, 891, 1122, 1413, 1778, 2239, 2818,
         3548, 4467, 5623, 7079, 8913, 11220, 14125, 16000]


def fit(x, n):
    """x stretched to n samples, band-limited (Fourier): for two runs of the same frames
    whose sample counts differ slightly (the core emits a whole number of samples a frame)."""
    if len(x) == n:
        return x
    spec = np.fft.rfft(x)
    out = np.zeros(n // 2 + 1, dtype=complex)
    m = min(len(spec), len(out))
    out[:m] = spec[:m]
    return np.fft.irfft(out, n) * (n / len(x))


def load(path):
    w = wave.open(path, "rb")
    rate, ch, width, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
    if width != 2:
        raise SystemExit("%s: 16-bit PCM expected" % path)
    x = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float64)
    w.close()
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate == RATE // 2:                       # the firmware's doubling (mame-go main.c audio_batch_cb)
        y = np.empty(len(x) * 2)
        if MIDPOINT:                            # the first version: each sample and the midpoint to the next
            y[0::2] = (np.concatenate(([0.0], x[:-1])) + x) / 2
            y[1::2] = x
            how = "16 kHz, doubled with the midpoint"
        else:                                   # each sample, and the 12-tap interpolation between two
            pad = np.concatenate((np.zeros(6), x, np.zeros(6)))
            y[0::2] = x
            y[1::2] = np.round(np.convolve(pad, TAPS, mode="valid")[1:len(x) + 1] / 4096.0)
            how = "16 kHz, doubled as the firmware does (12 taps)"
        x = y
    elif rate == RATE:
        how = "32 kHz"
    else:                                       # anything else (a microphone, a 44.1 kHz dump): band-limited
        x = fit(x, int(round(len(x) * RATE / rate)))
        how = "%d Hz, resampled" % rate
    return x, how


def bands(x):
    """Power per frame and band: array [frames, bands], plus the total power per frame."""
    n = 1 + (len(x) - FRAME) // HOP
    win = np.hanning(FRAME)
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(x[idx] * win, axis=1)) ** 2
    freqs = np.fft.rfftfreq(FRAME, 1.0 / RATE)
    out = np.stack([spec[:, (freqs >= lo) & (freqs < hi)].sum(axis=1) for lo, hi in zip(EDGES[:-1], EDGES[1:])], axis=1)
    return out, spec.sum(axis=1), spec, freqs


def db(p):
    return 10 * np.log10(np.maximum(p, 1e-12))


def align(a, b):
    """Offset of b against a (samples), from the loudness envelopes (100 Hz), within +-20 s."""
    step = RATE // 100
    ea = np.sqrt(np.add.reduceat(a[: len(a) // step * step] ** 2, np.arange(0, len(a) // step * step, step)))
    eb = np.sqrt(np.add.reduceat(b[: len(b) // step * step] ** 2, np.arange(0, len(b) // step * step, step)))
    ea, eb = ea - ea.mean(), eb - eb.mean()
    best, lag = -1e30, 0
    for l in range(-2000, 2001):
        x, y = (ea[l:], eb) if l >= 0 else (ea, eb[-l:])
        n = min(len(x), len(y))
        if n < 300:
            continue
        c = float(np.dot(x[:n], y[:n])) / n
        if c > best:
            best, lag = c, l
    return lag * step


def main():
    global MIDPOINT
    argv, args, window = sys.argv[1:], [], None
    while argv:
        a = argv.pop(0)
        if a == "--seconds" and argv:
            window = [float(v) for v in argv.pop(0).split("-")]
        elif a == "--midpoint":
            MIDPOINT = True
        elif not a.startswith("--"):
            args.append(a)
    if len(args) != 2:
        print(__doc__)
        return 2
    a, how_a = load(args[0])
    b, how_b = load(args[1])
    if "--align" in sys.argv:
        lag = align(a, b)
        a, b = (a[lag:], b) if lag >= 0 else (a, b[-lag:])
        print("aligned: the test starts %.2f s %s the reference" % (abs(lag) / RATE, "after" if lag >= 0 else "before"))
    elif "--same-frames" in sys.argv and abs(len(a) - len(b)) < 0.01 * len(a):
        # two dumps of the same frames: the core emits floor(rate / fps) samples a frame, so the
        # 16 kHz run is 2 x 266 = 532 samples a frame against 533 and drifts 0.1 s a minute
        print("same frames: the test (%.3f s) stretched to the reference's %.3f s" % (len(b) / RATE, len(a) / RATE))
        b = fit(b, len(a))
    if window:
        a, b = a[int(window[0] * RATE):int(window[1] * RATE)], b[int(window[0] * RATE):int(window[1] * RATE)]
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    print("reference: %s (%s), test: %s (%s), %.1f s compared" % (args[0], how_a, args[1], how_b, n / RATE))
    if n < RATE:
        print("less than a second in common: nothing to compare")
        return 2

    ba, ta, sa, freqs = bands(a)
    bb, tb, sb, _ = bands(b)
    level = db(np.mean(b ** 2)) - db(np.mean(a ** 2))
    hi = freqs >= 8000
    print("overall level: test %+.2f dB against the reference" % level)
    print("energy above 8 kHz: reference %.2f %% (%.1f dB below its total), test %.2f %% (%.1f dB below)" % (
        100 * sa[:, hi].sum() / sa.sum(), -db(sa[:, hi].sum() / sa.sum()),
        100 * sb[:, hi].sum() / sb.sum(), -db(sb[:, hi].sum() / sb.sum())))

    floor = db(ba.max()) - 50                   # a band counts in a frame when it is within 50 dB of the loudest
    print("\nband (Hz)       long-term   mean |diff|   95th pct   frames   extra")
    worst_mean = worst_p95 = worst_extra = 0.0
    for k, (lo, hi_) in enumerate(zip(EDGES[:-1], EDGES[1:])):
        la, lb = db(ba[:, k]), db(bb[:, k])
        active = la > floor
        longterm = db(bb[:, k].mean()) - db(ba[:, k].mean())
        # sound the reference does not have: the test clearly louder (6 dB) in a frame
        # where the test's band is itself within 40 dB of the loudest
        extra = 100.0 * np.mean((lb > floor + 10) & (lb - la > 6))
        if active.sum() < 20:
            print("%5d-%-6d   %+6.2f dB   (reference silent here)                  %5.1f %%" % (lo, hi_, longterm, extra))
        else:
            d = np.abs(lb[active] - la[active])
            print("%5d-%-6d   %+6.2f dB   %6.2f dB    %6.2f dB   %5d   %5.1f %%" % (
                lo, hi_, longterm, d.mean(), np.percentile(d, 95), active.sum(), extra))
            if hi_ <= 8913:
                worst_mean, worst_p95 = max(worst_mean, d.mean()), max(worst_p95, np.percentile(d, 95))
        if hi_ <= 8913:
            worst_extra = max(worst_extra, extra)

    print("\nbelow 8 kHz, worst band: mean |diff| %.2f dB, 95th percentile %.2f dB, extra sound in %.1f %% of the frames" % (
        worst_mean, worst_p95, worst_extra))
    if abs(level) < 0.5 and worst_mean < 1.0 and worst_p95 < 3.0 and worst_extra < 1.0:
        print("VERDICT: no difference a listener would be expected to hear below 8 kHz")
    elif abs(level) < 1.5 and worst_mean < 2.0 and worst_p95 < 6.0 and worst_extra < 5.0:
        print("VERDICT: small differences below 8 kHz; audible when compared side by side, unlikely to be noticed in play")
    else:
        print("VERDICT: differences below 8 kHz large enough to be heard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
