---
name: isolation-check
description: Verify every PCB conductor is connected where intended and isolated everywhere else — shorts between pads, holes, layers and zones, plus JLCPCB's published via/hole limits. Run after ANY change to routing, footprints, placement or the board outline.
disable-model-invocation: false
allowed-tools: Bash, Read, Grep, Glob
argument-hint: [ | --verbose | --list]
---

# Isolation Check

Answers two questions over the whole board, in about two seconds:

- **CONNECTED** — everything that should be one net IS one piece of copper
- **ISOLATED** — nothing that should be separate touches anything else

## Why this exists

`make verify-all` runs 70 gates (the list is `VERIFY_ALL_SCRIPTS` in the Makefile). But
before this gate, only five ran automatically when the PCB changed. Every
check answering *"is anything shorted to anything else?"* sat in the other
forty-eight — so it ran when somebody remembered, not when the board moved.

That gap is not theoretical. The `+3V3` plane was split into four separate
groups from the very first commit of the PCB file, and no v1 board ever had
3.3 V at the ESP32. The check that would have caught it existed.

## Run it

```bash
make verify-isolation                              # 13 checks, ~2s
python3 scripts/verify_isolation.py --verbose      # full output per check
python3 scripts/verify_isolation.py --list         # what it runs and why
```

It also runs automatically from the Stop hook whenever PCB files change, so
in normal work you do not invoke it — you notice when it complains.

## What it composes

| Check | Catches |
|---|---|
| `short_circuit_analysis` | different nets sharing copper |
| `verify_trace_through_pad` | netted trace crossing an unnetted pad (the v3.3 regression, `775e9fd`) |
| `verify_trace_crossings` | two segments meeting on one layer without a node — the fabricator merges them |
| `verify_copper_clearance` | copper-to-copper gaps under the fab minimum |
| `analyze_pad_distances` | pad-to-pad and pad-to-via spacing |
| `verify_via_in_pad` | a via landing inside a different-net SMD pad |
| `verify_zone_connectivity` | vias and THT pads actually reaching the fill |
| `verify_power_net_integrity` | each power net is ONE group |
| `verify_net_connectivity` | per-net union-find over the copper graph |
| `verify_component_connectivity` | phantom components with no copper at all |
| `verify_stackup` | nets on the layers the stackup declares |
| `verify_polarity` | every pad carries the net the design intends |
| `verify_jlcpcb_via_rules` | JLCPCB's published via/hole/slot limits |

## Reading the result

- **PASS** — clean.
- **FAIL** — something is shorted, unconnected, or on the wrong layer. Do not
  commit and do not order. Re-run that one script for detail.
- **MISS** — a member script is gone. This fails the gate too: a check that
  disappeared is lost coverage, not a pass.

`verify_jlcpcb_via_rules` additionally separates **HARD** (below a stated
manufacturing limit — fails) from **ADVISORY** (legal but surcharged, such as
the 308 vias drilled 0.20 mm against JLCPCB's 0.30 mm "small hole" threshold).
Advisories are always printed and never fail: they are cost decisions, and
failing on them would train people to ignore the gate.

## Proving it still works

The gate is mutation-tested, because an assertion that has never fired is not
evidence:

```bash
# a member that fails must surface as FAIL and exit 1
# a member that vanishes must surface as MISS and exit 1
```

Both were verified when the gate was built. If you add a check, verify it
fails on a planted defect before trusting it.

## Related

- `/verify` — the full 122-test DFM suite
- `/drc-audit` — KiCad native DRC
- `make verify-all` — all 70 gates
- [+3V3 split plane incident](/docs/rework/incident-3v3-split-plane)
