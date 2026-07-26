"""routing — split into domain modules 2026-07-26.

The public contract is unchanged: every name that lived at the top
level of the old routing.py is reachable as routing.<name>. Defs are
re-exported eagerly; everything else is forwarded LIVE to _shared via
PEP 562 __getattr__, because _init_pads() REBINDS _PADS/_PAD_NETS/
_PAD_POS_LOOKUP at runtime and an eager from-import would freeze the
pre-rebind objects (stale None seen by board._inject_pad_net).
"""
from . import _shared
from ._shared import (  # helper defs — never rebound
    _L,
    _compute_pads,
    _crosses_j1_front_shield,
    _crosses_slot,
    _esp_pin,
    _fpc_display_pin,
    _fpc_pin,
    _hv_route,
    _init_keepout_zones,
    _init_pads,
    _mh_detour_h,
    _pad,
    _pu_jog_vert,
    _seg,
    _segment_crosses_circle,
    _via_net,
    enc,
    get_collision_violations,
    get_pad_nets,
)
from .power import _buck_traces, _power_traces, _power_zones
from .display import _display_traces
from .sd import _spi_traces
from .audio import _i2s_traces, _pam_passive_traces
from .usb import _usb_c_reversibility_traces, _usb_traces
from .buttons import _button_pullup_bridges, _button_traces, _menu_diode_traces, _reset_boot_traces
from .passives import _led_traces, _passive_traces
from ._assemble import generate_all_traces


def __getattr__(name):
    # Live forwarding: constants AND the runtime-rebound tables (_PADS,
    # _PAD_NETS, _PAD_POS_LOOKUP, _KEEPOUT_CIRCLES, _MH_DETOUR_IDX).
    return getattr(_shared, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_shared)))
