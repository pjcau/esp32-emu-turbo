"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from .. import primitives as P
from ._shared import (
    NET_ID,
    _GRID,
    _MH_DETOUR_IDX,
    _PADS,
    _PAD_NETS,
    _PAD_POS_LOOKUP,
    _SEED_PAD_NETS,
    _init_keepout_zones,
)
from .buttons import _button_pullup_bridges
from .buttons import _button_traces
from .display import _display_traces
from .audio import _i2s_traces
from .passives import _diag_led_traces
from .passives import _led_traces
from .buttons import _menu_diode_traces
from .audio import _pam_passive_traces
from .passives import _passive_traces
from .power import _power_traces
from .power import _power_zones
from .buttons import _reset_boot_traces
from .sd import _spi_traces
from .usb import _usb_c_reversibility_traces
from .usb import _usb_traces




# ── Main entry point ──────────────────────────────────────────────

def generate_all_traces():
    """Generate all PCB traces and zones.

    Returns a single string of KiCad S-expressions.

    Routes the board TWICE, and the reason is the collision detector:

    A pad only learns its net when a trace endpoint lands on it
    (`_seg`/`_via_net` -> `_GRID.update_pad_net`). So on a single pass every
    pad starts at net 0, and net-0 pads used to be skipped by collision
    queries — which made the detector default-OPEN. A pad the router never
    targets never acquired a net, stayed invisible for the whole run, and a
    trace could be laid straight across it with nothing reported. The
    post-hoc gates (verify_trace_through_pad, short_circuit_analysis,
    analyze_pad_distances) were the only thing standing behind that.

    Pass 1 is a discovery run whose OUTPUT IS DISCARDED; all it is for is
    the pad->net map it leaves in `_PAD_NETS`. Pass 2 seeds the grid with
    that map before the first trace is placed, so every routed pad is known
    from the start and net 0 now means "unconnected copper" — a thing
    nothing may overlap — rather than "not known yet".

    Three properties this rests on, all checked by
    scripts/test_collision_pad_nets.py:

    - the pass is free of side effects on the emitted board. The collision
      result is only appended to `_GRID.violations`; `_seg`/`_via_net` place
      copper either way. Two consecutive runs are byte-identical.
    - the UUID counter is rewound between passes (`P.uid_restore`), so the
      emitted board is unchanged down to the ids.
    - the discovery pass prints no report. One run, one report.
    """
    # ── Pass 1: discovery ─────────────────────────────────────────
    _SEED_PAD_NETS.clear()
    _uid_mark = P.uid_mark()
    _route_once(report=False)
    _discovered = dict(_PAD_NETS)

    # ── Pass 2: the run that is emitted ───────────────────────────
    P.uid_restore(_uid_mark)
    _SEED_PAD_NETS.clear()
    _SEED_PAD_NETS.update(_discovered)
    return _route_once(report=True)


def _route_once(report: bool = True):
    """One full routing pass. See generate_all_traces for why there are two."""
    # Reset collision grid and pad state for fresh generation.
    #
    # IN PLACE, not rebound. This module and every domain module import
    # these tables eagerly from _shared; `global _PADS; _PADS = {}` here
    # would rebind _assemble's OWN binding, forking the state: the domains
    # and the final explicit assignments below would write to one dict
    # while board._inject_pad_net reads another. That exact fork silently
    # dropped U1.3=EN, U6.8/9 and SW16.4b/4d from the CPL pipeline when
    # routing.py was first split — caught by verify_trace_through_pad.
    _GRID.reset()
    _PADS.clear()
    _PAD_NETS.clear()
    _PAD_POS_LOOKUP.clear()

    # Initialize keepout zones from mounting holes
    _init_keepout_zones()
    # Reset detour Y counter for unique spacing
    _MH_DETOUR_IDX.clear()

    all_parts = []
    all_parts.extend(_power_traces())
    all_parts.extend(_display_traces())
    all_parts.extend(_spi_traces())
    all_parts.extend(_i2s_traces())
    all_parts.extend(_pam_passive_traces())
    all_parts.extend(_usb_traces())
    all_parts.extend(_usb_c_reversibility_traces())
    all_parts.extend(_button_traces())
    all_parts.extend(_passive_traces())
    all_parts.extend(_led_traces())
    all_parts.extend(_diag_led_traces())
    all_parts.extend(_reset_boot_traces())
    all_parts.extend(_menu_diode_traces())
    all_parts.extend(_button_pullup_bridges())
    all_parts.extend(_power_zones())

    # Report collision violations (discovery pass stays silent)
    if report:
        _GRID.print_report()

    # ── Explicit pad-net assignments ──────────────────────────────
    # Assign nets to pads that connect via zone fill or where the overlapping
    # trace IS the correct net for the pad (making it same-net = no DRC short).
    n_gnd = NET_ID["GND"]
    n_3v3 = NET_ID["+3V3"]
    # U3 pad nets are set by the explicit stubs in _buck_traces() — the old
    # override "U3.2 = +3V3" belonged to the AMS1117 SOT-223 (pin 2 = VOUT).
    # On the SY8089 SOT-23-5, pin 2 is GND; keeping the override would have
    # shorted the buck GND pin onto the +3V3 plane.
    _PAD_NETS[("U1", "3")] = NET_ID["EN"]  # EN pin, routed from SW15 via B.Cu

    # ── Trace-through-pad same-net fixups (restore commit 9709bea logic) ──
    # These assignments were ADDED in 9709bea to silence DRC shorts where a
    # netted trace physically passes over an unnetted pad. Commit 775e9fd
    # REMOVED them thinking they were NC pads — but verify_trace_through_pad
    # then flagged 6 real fab shorts. Restored with explicit safety analysis:
    #
    # U6.8 (SD DAT1): unused in SPI mode. The SD_MISO track physically
    #   overlaps this pad at the corridor between U6's rows; assigning the
    #   pad to SD_MISO makes the overlap same-net. Why the card does not
    #   drive it: NOT because of any CMD1/CMD0 tri-state claim (no held
    #   document says that), but because "the extended DAT lines (DAT1-DAT3)
    #   are input on power up" — SDCARD_SanDisk-Industrial-microSD_2016.pdf
    #   p.17 sec 3.1 table 3-1 footnote b — and in SPI mode contact 8 is RSV
    #   (table 3-2, p.18). The GPIO3 strap is latched at reset, inside the
    #   power-up window that footnote covers. Mechanism corrected 2026-07-31
    #   by the T3.3 protocol model (scripts/vbench/sdcard_protocol.py); the
    #   conclusion was right, the cited cause was not.
    #
    # U6.9 HAD THE SAME ENTRY AND IT WAS WRONG — see R31-HIGH-2. The
    #   argument above is about SD card contacts, and pad 9 is not one: a
    #   microSD card has eight, and this socket's ninth pad is the
    #   card-DETECT spring, which mates with the grounded shell. Borrowing
    #   pad 8's (valid) reasoning tied BTN_R/GPIO3 to a switch that grounds
    #   it in one card state. The BTN_R riser now detours east of the whole
    #   pad row (routing/buttons.py), the entry is gone, and pad 9 is back
    #   to no net. Do not reinstate it: a same-net entry here is a claim
    #   that the pad is inert, and this one is a switch to GND.
    #
    # SW16.4b/4d (shell anchor pads): mechanical retention tabs for the
    #   slide switch body, not electrical slide positions. Per
    #   datasheet_specs.py::SW16 these are _unconnected() with function
    #   "Shell/anchor (mechanical)". The shell metal is internally isolated
    #   from the slide signal terminals (1/2/3). BTN_SELECT vertical track
    #   at x=35.95 grazes pads 4b (36.4, 71.4) and 4d (36.4, 73.7) on the
    #   left edge (overlap 0.025mm). Same-net assignment connects the
    #   shell to BTN_SELECT, which is harmless because the shell is
    #   floating inside the component body.
    #
    #   That isolation is no longer just asserted here. CLAIM-001 in
    #   hardware/CLAIMS.md is VERIFIED-ON-DATASHEET: MSK12C02 spec section
    #   3.2 requires >=100 MOhm "across terminals, and across terminals and
    #   cover" at 100 V DC (PDF page 4, printed 2/8), and the manufacturer's
    #   own circuit diagram on the outline drawing draws terminal (4) — the
    #   four anchor pads — as a separate earth-symbol node joined to nothing.
    #
    # DO NOT REMOVE THESE without first rerouting the corresponding tracks.
    # `scripts/verify_trace_through_pad.py` is a hard gate and will block
    # release-prep if these overlaps reappear.
    _PAD_NETS[("U6", "8")] = NET_ID["SD_MISO"]
    _PAD_NETS[("SW16", "4b")] = NET_ID["BTN_SELECT"]
    _PAD_NETS[("SW16", "4d")] = NET_ID["BTN_SELECT"]

    return "".join(all_parts)
