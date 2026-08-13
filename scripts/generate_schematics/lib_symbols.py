"""KiCad library symbol definitions for all components."""

import re

# Each key is the symbol name used as lib_id
# Symbols needed per sheet are selected at render time

_SYMBOL_ESP32 = """    (symbol "ESP32-S3-WROOM-1" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 40.64 0) (effects (font (size 1.27 1.27))))
      (property "Value" "ESP32-S3-WROOM-1-N16R8" (at 0 -40.64 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "ESP32-S3-WROOM-1_0_1"
        (rectangle (start -12.7 39.37) (end 12.7 -39.37) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "ESP32-S3-WROOM-1_1_1"
        (pin power_in line (at -15.24 38.1 0) (length 2.54) (name "3V3" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -15.24 35.56 0) (length 2.54) (name "3V3" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin input line (at -15.24 33.02 0) (length 2.54) (name "EN" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 30.48 0) (length 2.54) (name "GPIO4" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 27.94 0) (length 2.54) (name "GPIO5" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 25.4 0) (length 2.54) (name "GPIO6" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 22.86 0) (length 2.54) (name "GPIO7" (effects (font (size 1.016 1.016)))) (number "7" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 20.32 0) (length 2.54) (name "GPIO15" (effects (font (size 1.016 1.016)))) (number "8" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 17.78 0) (length 2.54) (name "GPIO16" (effects (font (size 1.016 1.016)))) (number "9" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 15.24 0) (length 2.54) (name "GPIO17" (effects (font (size 1.016 1.016)))) (number "10" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 12.7 0) (length 2.54) (name "GPIO18" (effects (font (size 1.016 1.016)))) (number "11" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 10.16 0) (length 2.54) (name "GPIO8" (effects (font (size 1.016 1.016)))) (number "12" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 5.08 0) (length 2.54) (name "GPIO19" (effects (font (size 1.016 1.016)))) (number "13" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 2.54 0) (length 2.54) (name "GPIO20" (effects (font (size 1.016 1.016)))) (number "14" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 0 0) (length 2.54) (name "GPIO3" (effects (font (size 1.016 1.016)))) (number "15" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 -5.08 0) (length 2.54) (name "GPIO46" (effects (font (size 1.016 1.016)))) (number "16" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 -7.62 0) (length 2.54) (name "GPIO9" (effects (font (size 1.016 1.016)))) (number "17" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 -10.16 0) (length 2.54) (name "GPIO10" (effects (font (size 1.016 1.016)))) (number "18" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -15.24 -12.7 0) (length 2.54) (name "GPIO11" (effects (font (size 1.016 1.016)))) (number "19" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 38.1 180) (length 2.54) (name "GPIO12" (effects (font (size 1.016 1.016)))) (number "20" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 35.56 180) (length 2.54) (name "GPIO13" (effects (font (size 1.016 1.016)))) (number "21" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 33.02 180) (length 2.54) (name "GPIO14" (effects (font (size 1.016 1.016)))) (number "22" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 30.48 180) (length 2.54) (name "GPIO21" (effects (font (size 1.016 1.016)))) (number "23" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 27.94 180) (length 2.54) (name "GPIO47" (effects (font (size 1.016 1.016)))) (number "24" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 25.4 180) (length 2.54) (name "GPIO48" (effects (font (size 1.016 1.016)))) (number "25" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 22.86 180) (length 2.54) (name "GPIO45" (effects (font (size 1.016 1.016)))) (number "26" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 20.32 180) (length 2.54) (name "GPIO0" (effects (font (size 1.016 1.016)))) (number "27" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 17.78 180) (length 2.54) (name "GPIO35" (effects (font (size 1.016 1.016)))) (number "28" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 15.24 180) (length 2.54) (name "GPIO36" (effects (font (size 1.016 1.016)))) (number "29" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 12.7 180) (length 2.54) (name "GPIO37" (effects (font (size 1.016 1.016)))) (number "30" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 10.16 180) (length 2.54) (name "GPIO38" (effects (font (size 1.016 1.016)))) (number "31" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 7.62 180) (length 2.54) (name "GPIO39" (effects (font (size 1.016 1.016)))) (number "32" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 5.08 180) (length 2.54) (name "GPIO40" (effects (font (size 1.016 1.016)))) (number "33" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 2.54 180) (length 2.54) (name "GPIO41" (effects (font (size 1.016 1.016)))) (number "34" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 0 180) (length 2.54) (name "GPIO42" (effects (font (size 1.016 1.016)))) (number "35" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 -5.08 180) (length 2.54) (name "TX0" (effects (font (size 1.016 1.016)))) (number "36" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 -7.62 180) (length 2.54) (name "RX0" (effects (font (size 1.016 1.016)))) (number "37" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 -10.16 180) (length 2.54) (name "GPIO1" (effects (font (size 1.016 1.016)))) (number "38" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 15.24 -12.7 180) (length 2.54) (name "GPIO2" (effects (font (size 1.016 1.016)))) (number "39" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -41.91 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "40" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 2.54 -41.91 90) (length 2.54) (name "~" (effects (font (size 1.016 1.016)))) (number "41" (effects (font (size 1.016 1.016)))))))\n"""
# Pin 41's NAME is "~" (blank), not "GND": pins 40 and 41 sit 2.54 mm apart
# and both names printed inside the body overlapped into unreadable ink
# (verify_schematic_overlaps caught "GND × GND"). The pin NUMBER, type
# (power_in) and net are untouched — one visible GND name covers the pair.

_SYMBOL_SY8089 = """    (symbol "SY8089AAAC" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "SY8089AAAC" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "SY8089AAAC_0_1" (rectangle (start -6.35 5.08) (end 6.35 -5.08) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "SY8089AAAC_1_1"
        (pin power_in line (at -8.89 2.54 0) (length 2.54) (name "IN" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin input line (at -8.89 -2.54 0) (length 2.54) (name "EN" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -7.62 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin output line (at 8.89 2.54 180) (length 2.54) (name "LX" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin input line (at 8.89 -2.54 180) (length 2.54) (name "FB" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_C = """    (symbol "C" (pin_names (offset 0.254) hide) (in_bom yes) (on_board yes)
      (property "Reference" "C" (at 0.635 2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Value" "C" (at 0.635 -2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "C_0_1"
        (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))
        (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none))))
      (symbol "C_1_1"
        (pin passive line (at 0 3.81 270) (length 3.048) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 3.048) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_R = """    (symbol "R" (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at -1.778 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "R_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_SW_PUSH = """    (symbol "SW_Push" (pin_names (offset 1.016) hide) (in_bom yes) (on_board yes)
      (property "Reference" "SW" (at 1.27 2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Value" "SW_Push" (at 0 -1.524 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "SW_Push_0_1"
        (circle (center -2.032 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))
        (circle (center 2.032 0) (radius 0.508) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 1.524) (xy 0 3.048)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy -2.54 0) (xy 2.54 0)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "SW_Push_1_1"
        (pin passive line (at -5.08 0 0) (length 2.54) (name "1" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 5.08 0 180) (length 2.54) (name "2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_IP5306 = """    (symbol "IP5306" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 10.16 0) (effects (font (size 1.27 1.27))))
      (property "Value" "IP5306" (at 0 -10.16 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "Package_SO:ESOP-8" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "IP5306_0_1" (rectangle (start -7.62 7.62) (end 7.62 -7.62) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "IP5306_1_1"
        (pin power_in line (at -10.16 5.08 0) (length 2.54) (name "VIN" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin output line (at -10.16 2.54 0) (length 2.54) (name "LED1" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin output line (at -10.16 0 0) (length 2.54) (name "LED2" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin output line (at -10.16 -2.54 0) (length 2.54) (name "LED3" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin input line (at 10.16 -5.08 180) (length 2.54) (name "KEY" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 -2.54 180) (length 2.54) (name "BAT" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 10.16 0 180) (length 2.54) (name "SW" (effects (font (size 1.016 1.016)))) (number "7" (effects (font (size 1.016 1.016)))))
        (pin power_out line (at 10.16 5.08 180) (length 2.54) (name "VOUT" (effects (font (size 1.016 1.016)))) (number "8" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -10.16 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "9" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_L = """    (symbol "L" (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
      (property "Reference" "L" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "L" (at -1.778 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "L_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "L_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_JST_PH_2 = """    (symbol "Conn_JST_PH_2" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "JST_PH_2" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Conn_JST_PH_2_0_1" (rectangle (start -3.81 3.81) (end 3.81 -3.81) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "Conn_JST_PH_2_1_1"
        (pin passive line (at -6.35 1.27 0) (length 2.54) (name "+" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -6.35 -1.27 0) (length 2.54) (name "-" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_PAM8403 = """    (symbol "PAM8403_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "PAM8403" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PAM8403_Module_0_1" (rectangle (start -7.62 6.35) (end 7.62 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "PAM8403_Module_1_1"
        (pin power_in line (at -10.16 3.81 0) (length 2.54) (name "VCC" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -10.16 0 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 -3.81 0) (length 2.54) (name "AUDIO_IN" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin output line (at 10.16 3.81 180) (length 2.54) (name "SPK+" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin output line (at 10.16 0 180) (length 2.54) (name "SPK-" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin input line (at 10.16 -3.81 180) (length 2.54) (name "MUTE" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))\n"""
# Pin 6 "MUTE" (added with the J5 headphone jack): SOP-16 pin 5, active
# low with an internal pull-up (PAM8403 datasheet pin table). Freed from
# the historic +5V strap so the jack-detect transistor Q3 can pull it
# low. verify_netlist_diff maps it through _U5_MAP["6"] -> pad "5".
# Drawn on the RIGHT edge (below SPK-) — a bottom-center pin put its
# number on top of the Value text (verify_schematic_render_overlaps).

_SYMBOL_SD = """    (symbol "SD_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "SD_Card_SPI" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "SD_Module_0_1" (rectangle (start -7.62 6.35) (end 7.62 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "SD_Module_1_1"
        (pin power_in line (at -10.16 3.81 0) (length 2.54) (name "VCC" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -10.16 0 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin input line (at 10.16 3.81 180) (length 2.54) (name "MOSI" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin output line (at 10.16 0 180) (length 2.54) (name "MISO" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin input line (at 10.16 -3.81 180) (length 2.54) (name "CLK" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 -3.81 0) (length 2.54) (name "CS" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_ST7796S = """    (symbol "ST7796S_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 17.78 0) (effects (font (size 1.27 1.27))))
      (property "Value" "ST7796S_4.0_8080" (at 0 -17.78 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "ST7796S_Module_0_1" (rectangle (start -7.62 16.51) (end 7.62 -16.51) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "ST7796S_Module_1_1"
        (pin power_in line (at -10.16 15.24 0) (length 2.54) (name "VCC" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -10.16 12.7 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 10.16 0) (length 2.54) (name "CS" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 7.62 0) (length 2.54) (name "RST" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 5.08 0) (length 2.54) (name "DC" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 2.54 0) (length 2.54) (name "WR" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 0 0) (length 2.54) (name "RD" (effects (font (size 1.016 1.016)))) (number "7" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 15.24 180) (length 2.54) (name "D0" (effects (font (size 1.016 1.016)))) (number "8" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 12.7 180) (length 2.54) (name "D1" (effects (font (size 1.016 1.016)))) (number "9" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 10.16 180) (length 2.54) (name "D2" (effects (font (size 1.016 1.016)))) (number "10" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 7.62 180) (length 2.54) (name "D3" (effects (font (size 1.016 1.016)))) (number "11" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 5.08 180) (length 2.54) (name "D4" (effects (font (size 1.016 1.016)))) (number "12" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 2.54 180) (length 2.54) (name "D5" (effects (font (size 1.016 1.016)))) (number "13" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 0 180) (length 2.54) (name "D6" (effects (font (size 1.016 1.016)))) (number "14" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 -2.54 180) (length 2.54) (name "D7" (effects (font (size 1.016 1.016)))) (number "15" (effects (font (size 1.016 1.016)))))
        (pin input line (at -10.16 -5.08 0) (length 2.54) (name "BL" (effects (font (size 1.016 1.016)))) (number "16" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_BATTERY = """    (symbol "Battery" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "BT" (at 2.54 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "LiPo" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Battery_0_1"
        (polyline (pts (xy -1.27 1.27) (xy 1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 0.254) (xy 0.635 0.254)) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "Battery_1_1"
        (pin passive line (at 0 3.81 270) (length 2.54) (name "+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 2.54) (name "-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_USB_C = """    (symbol "USB_C" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "USB_C" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "USB_C_0_1" (rectangle (start -5.08 6.35) (end 5.08 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "USB_C_1_1"
        (pin power_out line (at 7.62 3.81 180) (length 2.54) (name "VBUS" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 0 180) (length 2.54) (name "CC1" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 -3.81 180) (length 2.54) (name "CC2" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -7.62 3.81 0) (length 2.54) (name "D+" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -7.62 0 0) (length 2.54) (name "D-" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -8.89 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_SPEAKER = """    (symbol "Speaker" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "LS" (at 2.54 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "Speaker" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Speaker_0_1"
        (rectangle (start -1.27 1.27) (end 0 -1.27) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0 1.27) (xy 2.54 3.81) (xy 2.54 -3.81) (xy 0 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "Speaker_1_1"
        (pin passive line (at -3.81 1.27 0) (length 2.54) (name "+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at -3.81 -1.27 0) (length 2.54) (name "-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_JOYSTICK = """    (symbol "PSP_Joystick" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "PSP_Joystick" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PSP_Joystick_0_1" (rectangle (start -5.08 6.35) (end 5.08 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "PSP_Joystick_1_1"
        (pin power_in line (at -7.62 3.81 0) (length 2.54) (name "VCC" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -7.62 0 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin output line (at 7.62 3.81 180) (length 2.54) (name "X_AXIS" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin output line (at 7.62 0 180) (length 2.54) (name "Y_AXIS" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_PWR_FLAG = """    (symbol "PWR_FLAG" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_GND = """    (symbol "GND" (power) (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -5.08 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_3V3 = """    (symbol "+3V3" (power) (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+3V3" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+3V3_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+3V3_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+3V3" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_5V = """    (symbol "+5V" (power) (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+5V" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+5V_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+5V_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+5V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_LED = """    (symbol "LED" (pin_names (offset 1.016) hide) (in_bom yes) (on_board yes)
      (property "Reference" "LED" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Value" "LED" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "LED_0_1"
        (polyline (pts (xy -1.27 -1.27) (xy -1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -1.27 0) (xy 1.27 1.27) (xy 1.27 -1.27) (xy -1.27 0)) (stroke (width 0.254) (type default)) (fill (type outline))))
      (symbol "LED_1_1"
        (pin passive line (at -3.81 0 0) (length 2.54) (name "A" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 3.81 0 180) (length 2.54) (name "K" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_BAT54C = """    (symbol "BAT54C" (pin_names (offset 1.016) hide) (in_bom yes) (on_board yes)
      (property "Reference" "D" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "BAT54C" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "BAT54C_0_1"
        (rectangle (start -2.54 2.54) (end 2.54 -2.54) (stroke (width 0.254) (type default)) (fill (type background)))
        (polyline (pts (xy -1.6 -1.5) (xy -0.6 -0.5) (xy -1.6 0.5) (xy -1.6 -1.5)) (stroke (width 0.254) (type default)) (fill (type outline)))
        (polyline (pts (xy -0.6 -1.5) (xy -0.6 0.5)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 1.6 -1.5) (xy 0.6 -0.5) (xy 1.6 0.5) (xy 1.6 -1.5)) (stroke (width 0.254) (type default)) (fill (type outline)))
        (polyline (pts (xy 0.6 -1.5) (xy 0.6 0.5)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.6 -0.5) (xy 0.6 -0.5)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0 -0.5) (xy 0 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -2.54 -1.27) (xy -1.6 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 2.54 -1.27) (xy 1.6 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "BAT54C_1_1"
        (pin passive line (at -5.08 -1.27 0) (length 2.54) (name "1" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 5.08 -1.27 180) (length 2.54) (name "2" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 0 5.08 270) (length 2.54) (name "3" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))))\n"""

# P-channel MOSFET, SOT-23 (AO3401A) — used by Q1 (battery reverse-polarity
# protection) and Q2 (the SW16 respin's +5V high-side load switch). The pin
# COORDINATES are identical to BAT54C's, because Q1/Q2 were originally drawn
# with that dual-diode symbol as a stand-in and every wire on sheet 01 lands
# on these exact points; only the ARTWORK changed (a diode pair drawn where a
# transistor sits is exactly the kind of "graphic that doesn't add up" a
# reviewer stumbles on). Numbers follow the SOT-23 pads:
#   1 = Gate  (enters left,  y=-1.27 local)
#   2 = Source (enters right, y=-1.27 local)
#   3 = Drain (enters top,   x=0 local)
# Arrow drawn on the source lead pointing AWAY from the channel = P-channel
# (KiCad Q_PMOS convention).
_SYMBOL_PMOS = """    (symbol "PMOS_SOT23" (pin_names (offset 0.508) hide) (in_bom yes) (on_board yes)
      (property "Reference" "Q" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "PMOS" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PMOS_SOT23_0_1"
        (polyline (pts (xy -1.27 -2.032) (xy -1.27 0.762)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 -2.286) (xy -0.635 1.016)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -2.54 -1.27) (xy -1.27 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 -1.27) (xy 2.54 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 0.762) (xy 0 0.762) (xy 0 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0.508 -0.889) (xy 1.27 -1.27) (xy 0.508 -1.651) (xy 0.508 -0.889)) (stroke (width 0.254) (type default)) (fill (type outline))))
      (symbol "PMOS_SOT23_1_1"
        (pin input line (at -5.08 -1.27 0) (length 2.54) (name "G" (effects (font (size 0.889 0.889)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 5.08 -1.27 180) (length 2.54) (name "S" (effects (font (size 0.889 0.889)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 0 5.08 270) (length 2.54) (name "D" (effects (font (size 0.889 0.889)))) (number "3" (effects (font (size 1.016 1.016)))))))\n"""

# N-channel MOSFET, SOT-23 (2N7002) — Q3, the headphone-jack mute
# driver. Same pin COORDINATES as PMOS_SOT23/BAT54C (see the PMOS note:
# every SOT-23 small-signal symbol in this library shares that grid so
# sheet wiring is interchangeable). Numbers follow the SOT-23 pads:
#   1 = Gate  (enters left,  y=-1.27 local)
#   2 = Source (enters right, y=-1.27 local)
#   3 = Drain (enters top,   x=0 local)
# Arrow drawn on the source lead pointing INTO the channel = N-channel
# (KiCad Q_NMOS convention, mirror of the PMOS arrow).
_SYMBOL_NMOS = """    (symbol "NMOS_SOT23" (pin_names (offset 0.508) hide) (in_bom yes) (on_board yes)
      (property "Reference" "Q" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "NMOS" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "NMOS_SOT23_0_1"
        (polyline (pts (xy -1.27 -2.032) (xy -1.27 0.762)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 -2.286) (xy -0.635 1.016)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -2.54 -1.27) (xy -1.27 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 -1.27) (xy 2.54 -1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 0.762) (xy 0 0.762) (xy 0 2.54)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0.762 -1.651) (xy 0 -1.27) (xy 0.762 -0.889) (xy 0.762 -1.651)) (stroke (width 0.254) (type default)) (fill (type outline))))
      (symbol "NMOS_SOT23_1_1"
        (pin input line (at -5.08 -1.27 0) (length 2.54) (name "G" (effects (font (size 0.889 0.889)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 5.08 -1.27 180) (length 2.54) (name "S" (effects (font (size 0.889 0.889)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 0 5.08 270) (length 2.54) (name "D" (effects (font (size 0.889 0.889)))) (number "3" (effects (font (size 1.016 1.016)))))))\n"""

# 3.5mm stereo headphone jack with switch contacts (HOOYA PJ-327A,
# LCSC C19712376). Pin NUMBERS are the footprint pad numbers — no
# verify_netlist_diff map needed. Roles from the HOOYA datasheet's
# plug-travel diagram (tip zone touches 2, ring zone 5, sleeve 3; 6 and
# 4 are the normally-closed rest contacts of 2 and 5 — they open when a
# plug is inserted):
#   2 = TIP (left)    5 = RING (right)    3 = SLEEVE (GND)
#   6 = TIPSW  — NC to 2 when unplugged (jack-detect input)
#   4 = RINGSW — NC to 5 when unplugged (unused here)
_SYMBOL_AUDIO_JACK = """    (symbol "AudioJack_PJ327A" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 8.89 0) (effects (font (size 1.27 1.27))))
      (property "Value" "PJ-327A" (at 0 -8.89 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "AudioJack_PJ327A_0_1"
        (rectangle (start -6.35 7.62) (end 6.35 -7.62) (stroke (width 0.254) (type default)) (fill (type background)))
        (circle (center -5.08 0) (radius 0.635) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "AudioJack_PJ327A_1_1"
        (pin passive line (at -8.89 5.08 0) (length 2.54) (name "TIP" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -8.89 2.54 0) (length 2.54) (name "RING" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -8.89 -2.54 0) (length 2.54) (name "SLV" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 8.89 5.08 180) (length 2.54) (name "TSW" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 8.89 -2.54 180) (length 2.54) (name "RSW" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))))\n"""
# Pin names SLV/TSW/RSW are abbreviated on purpose: the body is 12.7mm
# wide and "SLEEVE" x "RINGSW" met in the middle
# (verify_schematic_render_overlaps).

_SYMBOL_USBLC6_2SC6 = """    (symbol "USBLC6_2SC6" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "USBLC6-2SC6" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "USBLC6_2SC6_0_1" (rectangle (start -7.62 5.08) (end 7.62 -5.08) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "USBLC6_2SC6_1_1"
        (pin bidirectional line (at -10.16 2.54 0) (length 2.54) (name "I/O1_A" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -7.62 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at -10.16 0 0) (length 2.54) (name "I/O2_A" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 0 180) (length 2.54) (name "I/O2_B" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 7.62 270) (length 2.54) (name "VBUS" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 -2.54 180) (length 2.54) (name "I/O1_B" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))\n"""

# The symbol NAME is a drawing abstraction — J4 is physically a 40-pin FPC
# connector and only 16 of its pins carry a signal, so the schematic draws
# 16 pins (see sheets/display.py). The VALUE is not an abstraction: it names
# the part that gets fitted, and it must be the BOM's part or the BOM and the
# schematic are describing different components. It said "FPC-16P-0.5mm"
# until 2026-08-02, and verify_bom_values carried a KNOWN_MAPPINGS entry
# translating that to the 40-pin BOM comment — a gate agreeing to look away
# from a real disagreement. Value fixed, mapping deleted.
_SYMBOL_FPC_16P = """    (symbol "FPC_16P" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 21.59 0) (effects (font (size 1.27 1.27))))
      (property "Value" "FPC 40-pin 0.5mm Bottom Contact" (at 0 -21.59 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "FPC_16P_0_1" (rectangle (start -5.08 20.32) (end 5.08 -20.32) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "FPC_16P_1_1"
        (pin passive line (at -7.62 17.78 0) (length 2.54) (name "1" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 15.24 0) (length 2.54) (name "2" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 12.7 0) (length 2.54) (name "3" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 10.16 0) (length 2.54) (name "4" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 7.62 0) (length 2.54) (name "5" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 5.08 0) (length 2.54) (name "6" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 2.54 0) (length 2.54) (name "7" (effects (font (size 1.016 1.016)))) (number "7" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 0 0) (length 2.54) (name "8" (effects (font (size 1.016 1.016)))) (number "8" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -2.54 0) (length 2.54) (name "9" (effects (font (size 1.016 1.016)))) (number "9" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -5.08 0) (length 2.54) (name "10" (effects (font (size 1.016 1.016)))) (number "10" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -7.62 0) (length 2.54) (name "11" (effects (font (size 1.016 1.016)))) (number "11" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -10.16 0) (length 2.54) (name "12" (effects (font (size 1.016 1.016)))) (number "12" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -12.7 0) (length 2.54) (name "13" (effects (font (size 1.016 1.016)))) (number "13" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -15.24 0) (length 2.54) (name "14" (effects (font (size 1.016 1.016)))) (number "14" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -17.78 0) (length 2.54) (name "15" (effects (font (size 1.016 1.016)))) (number "15" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -7.62 -20.32 0) (length 2.54) (name "16" (effects (font (size 1.016 1.016)))) (number "16" (effects (font (size 1.016 1.016)))))))\n"""

# Registry: symbol name -> definition string
SYMBOLS: dict[str, str] = {
    "ESP32-S3-WROOM-1": _SYMBOL_ESP32,
    "SY8089AAAC": _SYMBOL_SY8089,
    "C": _SYMBOL_C,
    "R": _SYMBOL_R,
    "SW_Push": _SYMBOL_SW_PUSH,
    "IP5306": _SYMBOL_IP5306,
    "L": _SYMBOL_L,
    "Conn_JST_PH_2": _SYMBOL_JST_PH_2,
    "PAM8403_Module": _SYMBOL_PAM8403,
    "SD_Module": _SYMBOL_SD,
    "ST7796S_Module": _SYMBOL_ST7796S,
    "Battery": _SYMBOL_BATTERY,
    "USB_C": _SYMBOL_USB_C,
    "Speaker": _SYMBOL_SPEAKER,
    "PSP_Joystick": _SYMBOL_JOYSTICK,
    "LED": _SYMBOL_LED,
    "BAT54C": _SYMBOL_BAT54C,
    "PMOS_SOT23": _SYMBOL_PMOS,
    "NMOS_SOT23": _SYMBOL_NMOS,
    "AudioJack_PJ327A": _SYMBOL_AUDIO_JACK,
    "USBLC6_2SC6": _SYMBOL_USBLC6_2SC6,
    "FPC_16P": _SYMBOL_FPC_16P,
    "PWR_FLAG": _SYMBOL_PWR_FLAG,
    "GND": _SYMBOL_GND,
    "+3V3": _SYMBOL_3V3,
    "+5V": _SYMBOL_5V,
}


# Library nickname the schematics reference their symbols under. A bare
# lib_id ("R") makes every symbol instance warn "the current configuration
# does not include the symbol library ''" — 169 times, i.e. most of the
# ERC noise floor. The nickname resolves against hardware/kicad/
# sym-lib-table, which points at the generated emu.kicad_sym; cache and
# library are emitted from the same SYMBOLS dict, so KiCad can compare
# them and they can never disagree.
LIB_NICKNAME = "emu"


def _prefixed(name: str) -> str:
    """The symbol body with its OUTER name qualified as emu:<name>.

    Only the outer (symbol "<name>" gets the nickname — the unit
    sub-symbols ("R_0_1") stay bare, matching how KiCad itself writes a
    cached library symbol.
    """
    return SYMBOLS[name].replace(
        f'(symbol "{name}" ', f'(symbol "{LIB_NICKNAME}:{name}" ', 1)


def lib_symbols_block(needed: list[str]) -> str:
    """Return (lib_symbols ...) block with only the needed symbol defs."""
    parts = ["  (lib_symbols\n"]
    # Always include power symbols
    always = {"GND", "+3V3", "+5V"}
    for name in list(needed) + sorted(always - set(needed)):
        if name in SYMBOLS:
            parts.append(_prefixed(name))
    parts.append("  )\n")
    return "".join(parts)


def library_file() -> str:
    """The complete emu.kicad_sym — every symbol, bare names.

    Written next to the schematics so the sym-lib-table's
    ${KIPRJMOD}/emu.kicad_sym resolves. Same source strings as the
    embedded caches: a diff between library and cache is impossible by
    construction, so KiCad's cache-vs-library comparison stays quiet.
    """
    parts = [
        '(kicad_symbol_lib\n'
        '  (version 20231120)\n'
        '  (generator "generate_schematics")\n'
        '  (generator_version "9.0")\n'
    ]
    for name in sorted(SYMBOLS):
        parts.append(SYMBOLS[name])
    parts.append(')\n')
    return "".join(parts)


def sym_lib_table() -> str:
    """The project sym-lib-table declaring the emu library."""
    return (
        '(sym_lib_table\n'
        '  (version 7)\n'
        f'  (lib (name "{LIB_NICKNAME}")(type "KiCad")'
        '(uri "${KIPRJMOD}/emu.kicad_sym")(options "")'
        '(descr "ESP32 Emu Turbo generated symbols — source of truth is '
        'scripts/generate_schematics/lib_symbols.py"))\n'
        ')\n'
    )


def body_half_height(name: str) -> float:
    """Half-height of a symbol's drawn body, in mm (0 if it has no graphics).

    Derived from the symbol's own graphics rather than a per-part table, so a
    symbol that grows cannot silently start printing its Reference/Value
    across its own outline -- which is exactly what U3 (body +-5.08) did while
    the fields sat at +-5.
    """
    src = SYMBOLS.get(name)
    if not src:
        return 0.0
    ys = []
    for m in re.finditer(r"\(rectangle \(start ([\d.\-]+) ([\d.\-]+)\) \(end ([\d.\-]+) ([\d.\-]+)\)", src):
        ys += [float(m.group(2)), float(m.group(4))]
    for pl in re.finditer(r"\(polyline\s*\(pts((?:\s*\(xy [\d.\-]+ [\d.\-]+\))+)\)", src):
        for xy in re.finditer(r"\(xy [\d.\-]+ ([\d.\-]+)\)", pl.group(1)):
            ys.append(float(xy.group(1)))
    for c in re.finditer(r"\(circle \(center [\d.\-]+ ([\d.\-]+)\) \(radius ([\d.\-]+)\)", src):
        cy, rr = float(c.group(1)), float(c.group(2))
        ys += [cy - rr, cy + rr]
    return max((abs(y) for y in ys), default=0.0)


def body_half_width(name: str) -> float:
    """Half-width of a symbol's drawn body, in mm (0 if it has no graphics).

    Sister of body_half_height, for the sideways direction: field text placed
    BESIDE a two-pin part (see kicad_primitives.symbol) must clear the body's
    widest graphic — for "C" that is the 2.032 mm capacitor plates, twice the
    rectangle width of "R".
    """
    src = SYMBOLS.get(name)
    if not src:
        return 0.0
    xs = []
    for m in re.finditer(r"\(rectangle \(start ([\d.\-]+) [\d.\-]+\) \(end ([\d.\-]+) [\d.\-]+\)", src):
        xs += [float(m.group(1)), float(m.group(2))]
    for pl in re.finditer(r"\(polyline\s*\(pts((?:\s*\(xy [\d.\-]+ [\d.\-]+\))+)\)", src):
        for xy in re.finditer(r"\(xy ([\d.\-]+) [\d.\-]+\)", pl.group(1)):
            xs.append(float(xy.group(1)))
    for c in re.finditer(r"\(circle \(center ([\d.\-]+) [\d.\-]+\) \(radius ([\d.\-]+)\)", src):
        cx, rr = float(c.group(1)), float(c.group(2))
        xs += [cx - rr, cx + rr]
    return max((abs(x) for x in xs), default=0.0)
