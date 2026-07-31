"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    NET_ID,
    _GRID,
    _MH_DETOUR_IDX,
    _PADS,
    _PAD_NETS,
    _PAD_POS_LOOKUP,
    _init_keepout_zones,
)
from .buttons import _button_pullup_bridges
from .buttons import _button_traces
from .display import _display_traces
from .audio import _i2s_traces
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
    """
    # Reset collision grid and pad state for fresh generation.
    #
    # IN PLACE, not rebound. This module and every domain module import
    # these tables eagerly from _shared; `global _PADS; _PADS = {}` here
    # would rebind _assemble's OWN binding, forking the state: the domains
    # and the final explicit assignments below would write to one dict
    # while board._inject_pad_net reads another. That exact fork silently
    # dropped U1.3=EN, U6.8/9 and SW_PWR.4b/4d from the CPL pipeline when
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
    all_parts.extend(_reset_boot_traces())
    all_parts.extend(_menu_diode_traces())
    all_parts.extend(_button_pullup_bridges())
    all_parts.extend(_power_zones())

    # Report collision violations
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
    _PAD_NETS[("U1", "3")] = NET_ID["EN"]  # EN pin, routed from SW_RST via B.Cu

    # ── Trace-through-pad same-net fixups (restore commit 9709bea logic) ──
    # These assignments were ADDED in 9709bea to silence DRC shorts where a
    # netted trace physically passes over an unnetted pad. Commit 775e9fd
    # REMOVED them thinking they were NC pads — but verify_trace_through_pad
    # then flagged 6 real fab shorts. Restored with explicit safety analysis:
    #
    # U6.8 (SD DAT1) / U6.9 (SD DAT2): unused in SPI mode. SD_MISO and
    #   BTN_R tracks physically overlap these pads at the corridor between
    #   U6 rows. Assigning them to SD_MISO/BTN_R nets makes the overlap
    #   same-net. Why the card does not drive them: NOT because of any
    #   CMD1/CMD0 tri-state claim (no held document says that), but because
    #   "the extended DAT lines (DAT1-DAT3) are input on power up" —
    #   SDCARD_SanDisk-Industrial-microSD_2016.pdf p.17 sec 3.1 table 3-1
    #   footnote b — and in SPI mode contacts 8/9 are RSV (table 3-2,
    #   p.18). The GPIO3 strap is latched at reset, inside the power-up
    #   window that footnote covers. Mechanism corrected 2026-07-31 by the
    #   T3.3 protocol model (scripts/vbench/sdcard_protocol.py); the
    #   conclusion was right, the cited cause was not.
    #
    # SW_PWR.4b/4d (shell anchor pads): mechanical retention tabs for the
    #   slide switch body, not electrical slide positions. Per
    #   datasheet_specs.py::SW_PWR these are _unconnected() with function
    #   "Shell/anchor (mechanical)". The shell metal is internally isolated
    #   from the slide signal terminals (1/2/3). BTN_SELECT vertical track
    #   at x=35.95 grazes pads 4b (36.4, 71.4) and 4d (36.4, 73.7) on the
    #   left edge (overlap 0.025mm). Same-net assignment connects the
    #   shell to BTN_SELECT, which is harmless because the shell is
    #   floating inside the component body.
    #
    # DO NOT REMOVE THESE without first rerouting the corresponding tracks.
    # `scripts/verify_trace_through_pad.py` is a hard gate and will block
    # release-prep if these overlaps reappear.
    _PAD_NETS[("U6", "8")] = NET_ID["SD_MISO"]
    _PAD_NETS[("U6", "9")] = NET_ID["BTN_R"]
    _PAD_NETS[("SW_PWR", "4b")] = NET_ID["BTN_SELECT"]
    _PAD_NETS[("SW_PWR", "4d")] = NET_ID["BTN_SELECT"]

    return "".join(all_parts)
