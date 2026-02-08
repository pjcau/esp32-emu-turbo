#!/usr/bin/env python3
"""Generate complete KiCad 9.0 schematic for ESP32 Emu Turbo.
Produces hardware/kicad/esp32-emu-turbo.kicad_sch with all components
wired via net labels, power symbols, and debounce capacitors.
"""
import sys, os

# --- GPIO mapping (source of truth: website/docs/snes-hardware.md) ---
GPIO_NETS = {
    4:"LCD_D0", 5:"LCD_D1", 6:"LCD_D2", 7:"LCD_D3",
    8:"LCD_D4", 9:"LCD_D5", 10:"LCD_D6", 11:"LCD_D7",
    12:"LCD_CS", 13:"LCD_RST", 14:"LCD_DC", 46:"LCD_WR",
    3:"LCD_RD", 45:"LCD_BL",
    36:"SD_MOSI", 37:"SD_MISO", 38:"SD_CLK", 39:"SD_CS",
    15:"I2S_BCLK", 16:"I2S_LRCK", 17:"I2S_DOUT",
    40:"BTN_UP", 41:"BTN_DOWN", 42:"BTN_LEFT", 1:"BTN_RIGHT",
    2:"BTN_A", 48:"BTN_B", 47:"BTN_X", 21:"BTN_Y",
    18:"BTN_START", 0:"BTN_SELECT", 35:"BTN_L", 19:"BTN_R",
    20:"JOY_X", 44:"JOY_Y",
}

# ESP32-S3 pin# -> (side, gpio#_or_name, y_offset_from_center)
# side: L=left, R=right, B=bottom
ESP_PINS = {
    1:("L","3V3",38.1), 2:("L","3V3",35.56), 3:("L","EN",33.02),
    4:("L",4,30.48), 5:("L",5,27.94), 6:("L",6,25.4), 7:("L",7,22.86),
    8:("L",15,20.32), 9:("L",16,17.78), 10:("L",17,15.24), 11:("L",18,12.7),
    12:("L",8,10.16), 13:("L",19,5.08), 14:("L",20,2.54), 15:("L",3,0),
    16:("L",46,-5.08), 17:("L",9,-7.62), 18:("L",10,-10.16), 19:("L",11,-12.7),
    20:("R",12,38.1), 21:("R",13,35.56), 22:("R",14,33.02), 23:("R",21,30.48),
    24:("R",47,27.94), 25:("R",48,25.4), 26:("R",45,22.86), 27:("R",0,20.32),
    28:("R",35,17.78), 29:("R",36,15.24), 30:("R",37,12.7), 31:("R",38,10.16),
    32:("R",39,7.62), 33:("R",40,5.08), 34:("R",41,2.54), 35:("R",42,0),
    36:("R","TX0",-5.08), 37:("R","RX0",-7.62), 38:("R",1,-10.16), 39:("R",2,-12.7),
    40:("B","GND",0), 41:("B","GND",2.54),
}

_n = 0
def uid():
    global _n; _n += 1
    return f"{_n:08x}-cafe-4000-8000-{_n:012x}"

def W(x1,y1,x2,y2):
    return f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2})) (stroke (width 0) (type default)) (uuid "{uid()}"))\n'

def L(name,x,y,a=0):
    return f'  (label "{name}" (at {x} {y} {a}) (effects (font (size 1.27 1.27))) (uuid "{uid()}"))\n'

def T(txt,x,y,sz=2.54,bold=False):
    b = " bold" if bold else ""
    return f'  (text "{txt}" (at {x} {y} 0) (effects (font (size {sz} {sz}){b}) (justify left)))\n'

def PWR(lib,ref,val,x,y):
    return (f'  (symbol (lib_id "{lib}") (at {x} {y} 0) (unit 1) (exclude_from_sim no)'
            f' (in_bom no) (on_board no) (dnp no) (uuid "{uid()}")'
            f' (property "Reference" "{ref}" (at {x} {y-2} 0) (effects (font (size 1.27 1.27)) hide))'
            f' (property "Value" "{val}" (at {x} {y+2} 0) (effects (font (size 1.27 1.27)) hide))'
            f' (pin "1" (uuid "{uid()}")))\n')

_pn = 0
def gnd(x,y):
    global _pn; _pn+=1; return PWR("GND",f"#PWR{_pn:03d}","GND",x,y)
def v33(x,y):
    global _pn; _pn+=1; return PWR("+3V3",f"#PWR{_pn:03d}","+3V3",x,y)
def v5(x,y):
    global _pn; _pn+=1; return PWR("+5V",f"#PWR{_pn:03d}","+5V",x,y)

def SYM(lib,ref,val,x,y,pins):
    s = (f'  (symbol (lib_id "{lib}") (at {x} {y} 0) (unit 1) (exclude_from_sim no)'
         f' (in_bom yes) (on_board yes) (dnp no) (uuid "{uid()}")'
         f' (property "Reference" "{ref}" (at {x} {y-5} 0) (effects (font (size 1.27 1.27))))'
         f' (property "Value" "{val}" (at {x} {y+5} 0) (effects (font (size 1.27 1.27))))')
    for p in pins:
        s += f' (pin "{p}" (uuid "{uid()}"))'
    return s + ')\n'

# ====================== LIBRARY SYMBOLS ======================
# (large block, kept as raw string for speed)
LIB = open(os.path.join(os.path.dirname(__file__), "lib_symbols.kicad"), "r").read() if os.path.exists(os.path.join(os.path.dirname(__file__), "lib_symbols.kicad")) else None

def lib_symbols():
    """Generate all library symbol definitions inline."""
    # Instead of external file, embed them
    return r"""  (lib_symbols
    (symbol "ESP32-S3-WROOM-1" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin power_in line (at 2.54 -41.91 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "41" (effects (font (size 1.016 1.016)))))))
    (symbol "AMS1117-3.3" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "AMS1117-3.3" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "AMS1117-3.3_0_1" (rectangle (start -5.08 3.81) (end 5.08 -3.81) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "AMS1117-3.3_1_1"
        (pin power_in line (at -7.62 2.54 0) (length 2.54) (name "VIN" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -6.35 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin power_out line (at 7.62 2.54 180) (length 2.54) (name "VOUT" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))))
    (symbol "C" (pin_names (offset 0.254) hide) (in_bom yes) (on_board yes)
      (property "Reference" "C" (at 0.635 2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Value" "C" (at 0.635 -2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "C_0_1"
        (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))
        (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none))))
      (symbol "C_1_1"
        (pin passive line (at 0 3.81 270) (length 3.048) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 3.048) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
    (symbol "R" (pin_names (offset 0) hide) (in_bom yes) (on_board yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at -1.778 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "R_0_1" (rectangle (start -1.016 -2.54) (end 1.016 2.54) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27) (name "~" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
    (symbol "SW_Push" (pin_names (offset 1.016) hide) (in_bom yes) (on_board yes)
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
        (pin passive line (at 5.08 0 180) (length 2.54) (name "2" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
    (symbol "IP5306_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "IP5306_USB-C_Module" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "IP5306_Module_0_1" (rectangle (start -7.62 6.35) (end 7.62 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "IP5306_Module_1_1"
        (pin power_in line (at -10.16 3.81 0) (length 2.54) (name "USB_5V" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -10.16 0 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 3.81 180) (length 2.54) (name "BAT+" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin bidirectional line (at 10.16 0 180) (length 2.54) (name "BAT-" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))
        (pin power_out line (at 10.16 -3.81 180) (length 2.54) (name "OUT_5V" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))))
    (symbol "PAM8403_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin output line (at 10.16 0 180) (length 2.54) (name "SPK-" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))))
    (symbol "SD_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin input line (at -10.16 -3.81 0) (length 2.54) (name "CS" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))
    (symbol "ST7796S_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin input line (at -10.16 -5.08 0) (length 2.54) (name "BL" (effects (font (size 1.016 1.016)))) (number "16" (effects (font (size 1.016 1.016)))))))
    (symbol "Battery" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "BT" (at 2.54 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "LiPo" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Battery_0_1"
        (polyline (pts (xy -1.27 1.27) (xy 1.27 1.27)) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy -0.635 0.254) (xy 0.635 0.254)) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "Battery_1_1"
        (pin passive line (at 0 3.81 270) (length 2.54) (name "+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 2.54) (name "-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
    (symbol "USB_C" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin power_in line (at 0 -8.89 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "6" (effects (font (size 1.016 1.016)))))))
    (symbol "Speaker" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "LS" (at 2.54 2.54 0) (effects (font (size 1.27 1.27))))
      (property "Value" "Speaker" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "Speaker_0_1"
        (rectangle (start -1.27 1.27) (end 0 -1.27) (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0 1.27) (xy 2.54 3.81) (xy 2.54 -3.81) (xy 0 -1.27)) (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "Speaker_1_1"
        (pin passive line (at -3.81 0.635 0) (length 2.54) (name "+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at -3.81 -0.635 0) (length 2.54) (name "-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))
    (symbol "PSP_Joystick" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (at 0 7.62 0) (effects (font (size 1.27 1.27))))
      (property "Value" "PSP_Joystick" (at 0 -7.62 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PSP_Joystick_0_1" (rectangle (start -5.08 6.35) (end 5.08 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "PSP_Joystick_1_1"
        (pin power_in line (at -7.62 3.81 0) (length 2.54) (name "VCC" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at -7.62 0 0) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin output line (at 7.62 3.81 180) (length 2.54) (name "X_AXIS" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin output line (at 7.62 0 180) (length 2.54) (name "Y_AXIS" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))))
    (symbol "PWR_FLAG" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#FLG" (at 0 1.905 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "PWR_FLAG" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) (name "pwr" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))
    (symbol "GND" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -5.08 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))
    (symbol "+3V3" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+3V3" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+3V3_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+3V3_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+3V3" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))
    (symbol "+5V" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+5V" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+5V_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+5V_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+5V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))
  )
"""

# ====================== SCHEMATIC GENERATION ======================
MCU_X, MCU_Y = 101.6, 134.62

def generate():
    o = []
    o.append('(kicad_sch\n  (version 20231120)\n  (generator "eeschema")\n  (generator_version "9.0")\n')
    o.append('  (uuid "e63e39d7-6ac0-4ffd-8aa3-1841a4541b55")\n  (paper "A2")\n\n')
    o.append(lib_symbols())

    # ---- POWER SUPPLY ----
    o.append(T("=== POWER SUPPLY ===", 25.4, 12.7, 3.81, True))
    o.append(T("USB-C -> IP5306 -> AMS1117 -> 3.3V", 25.4, 17.78))
    o.append(SYM("USB_C","J1","USB_C",38.1,45.72,range(1,7)))
    o.append(SYM("R","R1","5.1k",53.34,50.8,["1","2"]))
    o.append(SYM("R","R2","5.1k",60.96,50.8,["1","2"]))
    o.append(W(45.72,45.72,53.34,45.72)+W(53.34,45.72,53.34,46.99))  # CC1->R1
    o.append(W(45.72,49.53,60.96,49.53)+W(60.96,49.53,60.96,46.99))  # CC2->R2
    o.append(gnd(53.34,57.15)+W(53.34,54.61,53.34,57.15))
    o.append(gnd(60.96,57.15)+W(60.96,54.61,60.96,57.15))
    o.append(gnd(38.1,57.15)+W(38.1,54.61,38.1,57.15))  # USB GND
    o.append(W(45.72,41.91,78.74,41.91))  # VBUS -> IP5306
    o.append(SYM("IP5306_Module","U2","IP5306_USB-C",88.9,45.72,range(1,6)))
    o.append(gnd(78.74,55.88)+W(78.74,45.72,78.74,55.88))
    # Battery
    o.append(SYM("Battery","BT1","LiPo 3.7V 5000mAh",116.84,45.72,["1","2"]))
    o.append(W(99.06,41.91,116.84,41.91)+W(116.84,41.91,116.84,41.91))  # BAT+
    o.append(W(99.06,45.72,116.84,45.72))  # BAT-
    o.append(gnd(116.84,55.88)+W(116.84,49.53,116.84,55.88))
    # 5V rail
    o.append(W(99.06,49.53,127,49.53))
    o.append(v5(127,44.45)+W(127,44.45,127,49.53))
    # AMS1117
    o.append(SYM("C","C1","10uF",134.62,49.53,["1","2"]))
    o.append(W(127,49.53,134.62,45.72)+gnd(134.62,57.15)+W(134.62,53.34,134.62,57.15))
    o.append(SYM("AMS1117-3.3","U3","AMS1117-3.3",149.86,44.45,["1","2","3"]))
    o.append(W(134.62,45.72,142.24,46.99))  # C1 -> VIN
    o.append(gnd(149.86,55.88)+W(149.86,50.8,149.86,55.88))
    o.append(SYM("C","C2","22uF tantalum",165.1,49.53,["1","2"]))
    o.append(W(157.48,46.99,165.1,46.99)+W(165.1,46.99,165.1,45.72))
    o.append(gnd(165.1,57.15)+W(165.1,53.34,165.1,57.15))
    o.append(v33(165.1,40.64)+W(165.1,40.64,165.1,45.72))

    # ---- MCU ----
    o.append(T("=== MCU - ESP32-S3-WROOM-1 N16R8 ===", 25.4, 76.2, 3.81, True))
    o.append(SYM("ESP32-S3-WROOM-1","U1","ESP32-S3-N16R8",MCU_X,MCU_Y,range(1,42)))
    # 3V3 power to MCU
    px = MCU_X - 15.24  # left pin x = 86.36
    o.append(W(px,MCU_Y-38.1,px-7.62,MCU_Y-38.1))  # pin1
    o.append(v33(px-7.62,MCU_Y-40.64)+W(px-7.62,MCU_Y-40.64,px-7.62,MCU_Y-38.1))
    o.append(W(px,MCU_Y-35.56,px-7.62,MCU_Y-35.56)+W(px-7.62,MCU_Y-38.1,px-7.62,MCU_Y-35.56))
    # EN pull-up + reset cap
    o.append(SYM("R","R3","10k",px-10.16,MCU_Y-27.94,["1","2"]))
    o.append(W(px,MCU_Y-33.02,px-10.16,MCU_Y-33.02)+W(px-10.16,MCU_Y-33.02,px-10.16,MCU_Y-31.75))
    o.append(v33(px-10.16,MCU_Y-38.1)+W(px-10.16,MCU_Y-38.1,px-10.16,MCU_Y-24.13))
    o.append(SYM("C","C3","100nF",px-15.24,MCU_Y-27.94,["1","2"]))
    o.append(W(px-10.16,MCU_Y-33.02,px-15.24,MCU_Y-33.02)+W(px-15.24,MCU_Y-33.02,px-15.24,MCU_Y-24.13))
    o.append(gnd(px-15.24,MCU_Y-20.32)+W(px-15.24,MCU_Y-24.13,px-15.24,MCU_Y-20.32))
    # Decoupling caps
    o.append(SYM("C","C4","100nF",px-7.62,MCU_Y-30.48,["1","2"]))
    o.append(gnd(px-7.62,MCU_Y-22.86)+W(px-7.62,MCU_Y-26.67,px-7.62,MCU_Y-22.86))
    # GND pins
    o.append(W(MCU_X,MCU_Y+41.91,MCU_X,MCU_Y+46.99)+gnd(MCU_X,MCU_Y+46.99))
    o.append(W(MCU_X+2.54,MCU_Y+41.91,MCU_X+2.54,MCU_Y+46.99)+gnd(MCU_X+2.54,MCU_Y+46.99))

    # GPIO net labels on ESP32 pins
    for pn, (side, gpio, yoff) in ESP_PINS.items():
        if side == "B" or gpio in ("3V3","EN","GND"):
            continue
        if side == "L":
            pin_x, pin_y = MCU_X - 15.24, MCU_Y - yoff
            lx = pin_x - 10.16
            o.append(W(pin_x,pin_y,lx,pin_y))
            net = GPIO_NETS.get(gpio, f"GPIO{gpio}" if isinstance(gpio,int) else gpio)
            o.append(L(net, lx, pin_y, 180))
        else:  # R
            pin_x, pin_y = MCU_X + 15.24, MCU_Y - yoff
            lx = pin_x + 10.16
            o.append(W(pin_x,pin_y,lx,pin_y))
            if isinstance(gpio, int):
                net = GPIO_NETS.get(gpio, f"GPIO{gpio}")
            elif gpio == "TX0":
                net = "UART_TX0"
            elif gpio == "RX0":
                net = GPIO_NETS.get(44, "JOY_Y")
            else:
                net = gpio
            o.append(L(net, lx, pin_y, 0))

    # ---- DISPLAY ----
    DX, DY = 270, 55.88
    o.append(T('=== DISPLAY - ST7796S 4.0" 8080 Parallel ===', 220, 12.7, 3.81, True))
    o.append(SYM("ST7796S_Module","U4","ST7796S 4.0in 8080",DX,DY,range(1,17)))
    o.append(v33(DX-17.78,DY-17.78)+W(DX-17.78,DY-17.78,DX-17.78,DY-15.24)+W(DX-10.16,DY-15.24,DX-17.78,DY-15.24))
    o.append(gnd(DX-17.78,DY-7.62)+W(DX-17.78,DY-7.62,DX-17.78,DY-12.7)+W(DX-10.16,DY-12.7,DX-17.78,DY-12.7))
    for pin,net,yoff in [(3,"LCD_CS",-10.16),(4,"LCD_RST",-7.62),(5,"LCD_DC",-5.08),(6,"LCD_WR",-2.54),(7,"LCD_RD",0),(16,"LCD_BL",5.08)]:
        o.append(W(DX-10.16,DY+yoff,DX-22.86,DY+yoff)+L(net,DX-22.86,DY+yoff,180))
    for pin,net,yoff in [(8,"LCD_D0",-15.24),(9,"LCD_D1",-12.7),(10,"LCD_D2",-10.16),(11,"LCD_D3",-7.62),(12,"LCD_D4",-5.08),(13,"LCD_D5",-2.54),(14,"LCD_D6",0),(15,"LCD_D7",2.54)]:
        o.append(W(DX+10.16,DY+yoff,DX+20.32,DY+yoff)+L(net,DX+20.32,DY+yoff,0))

    # ---- AUDIO ----
    AX, AY = 270, 116.84
    o.append(T("=== AUDIO - I2S -> PAM8403 -> Speaker ===", 220, 88.9, 3.81, True))
    o.append(T("GPIO15=BCLK GPIO16=LRCK GPIO17=DOUT", 220, 93.98))
    o.append(SYM("PAM8403_Module","U5","PAM8403",AX,AY,range(1,6)))
    o.append(v5(AX-17.78,AY-6.35)+W(AX-17.78,AY-6.35,AX-17.78,AY-3.81)+W(AX-10.16,AY-3.81,AX-17.78,AY-3.81))
    o.append(gnd(AX-17.78,AY+5.08)+W(AX-17.78,AY+5.08,AX-17.78,AY)+W(AX-10.16,AY,AX-17.78,AY))
    o.append(W(AX-10.16,AY+3.81,AX-22.86,AY+3.81)+L("I2S_DOUT",AX-22.86,AY+3.81,180))
    o.append(SYM("Speaker","LS1","28mm 8ohm",AX+30.48,AY,["1","2"]))
    o.append(W(AX+10.16,AY-3.81,AX+26.67,AY-0.635))  # SPK+
    o.append(W(AX+10.16,AY,AX+26.67,AY+0.635))  # SPK-

    # ---- SD CARD ----
    SX, SY = 270, 170.18
    o.append(T("=== STORAGE - SD Card SPI ===", 220, 147.32, 3.81, True))
    o.append(SYM("SD_Module","U6","SD_Card_SPI",SX,SY,range(1,7)))
    o.append(v33(SX-17.78,SY-6.35)+W(SX-17.78,SY-6.35,SX-17.78,SY-3.81)+W(SX-10.16,SY-3.81,SX-17.78,SY-3.81))
    o.append(gnd(SX-17.78,SY+5.08)+W(SX-17.78,SY+5.08,SX-17.78,SY)+W(SX-10.16,SY,SX-17.78,SY))
    o.append(W(SX+10.16,SY-3.81,SX+20.32,SY-3.81)+L("SD_MOSI",SX+20.32,SY-3.81,0))
    o.append(W(SX+10.16,SY,SX+20.32,SY)+L("SD_MISO",SX+20.32,SY,0))
    o.append(W(SX+10.16,SY+3.81,SX+20.32,SY+3.81)+L("SD_CLK",SX+20.32,SY+3.81,0))
    o.append(W(SX-10.16,SY+3.81,SX-20.32,SY+3.81)+L("SD_CS",SX-20.32,SY+3.81,180))

    # ---- BUTTONS (12x with pull-up + debounce) ----
    o.append(T("=== INPUT - 12 Buttons + Joystick ===", 25.4, 198.12, 3.81, True))
    o.append(T("Active-low: 10k pull-up + 100nF debounce + tact switch", 25.4, 203.2))
    buttons = [
        ("UP","BTN_UP","SW1","R4","C5",38,218),("DOWN","BTN_DOWN","SW2","R5","C6",38,233),
        ("LEFT","BTN_LEFT","SW3","R6","C7",38,248),("RIGHT","BTN_RIGHT","SW4","R7","C8",38,263),
        ("A","BTN_A","SW5","R8","C9",83,218),("B","BTN_B","SW6","R9","C10",83,233),
        ("X","BTN_X","SW7","R10","C11",83,248),("Y","BTN_Y","SW8","R11","C12",83,263),
        ("START","BTN_START","SW9","R12","C13",128,218),("SELECT","BTN_SELECT","SW10","R13","C14",128,233),
        ("L","BTN_L","SW11","R14","C15",128,248),("R","BTN_R","SW12","R15","C16",128,263),
    ]
    for name,net,sw,rr,cc,bx,by in buttons:
        # Pull-up resistor
        o.append(SYM("R",rr,"10k",bx,by-7.62,["1","2"]))
        o.append(v33(bx,by-15.24)+W(bx,by-15.24,bx,by-11.43))
        # Debounce cap
        o.append(SYM("C",cc,"100nF",bx+7.62,by-2.54,["1","2"]))
        o.append(W(bx,by-3.81,bx,by)+W(bx,by,bx+7.62,by)+W(bx+7.62,by,bx+7.62,by+1.27))
        o.append(gnd(bx+7.62,by+5.08)+W(bx+7.62,by-6.35,bx+7.62,by+5.08))
        # Switch
        o.append(SYM("SW_Push",sw,name,bx,by+5.08,["1","2"]))
        o.append(W(bx,by,bx-5.08,by+5.08))
        o.append(gnd(bx+5.08,by+10.16)+W(bx+5.08,by+5.08,bx+5.08,by+10.16))
        # Net label
        o.append(W(bx,by,bx+15.24,by)+L(net,bx+15.24,by,0))

    # Joystick
    o.append(SYM("PSP_Joystick","J2","PSP_Joystick",55,295,range(1,5)))
    o.append(v33(39.78,288.65)+W(39.78,288.65,39.78,291.19)+W(47.38,291.19,39.78,291.19))
    o.append(gnd(39.78,300.04)+W(39.78,300.04,39.78,295)+W(47.38,295,39.78,295))
    o.append(W(62.62,291.19,76.2,291.19)+L("JOY_X",76.2,291.19,0))
    o.append(W(62.62,295,76.2,295)+L("JOY_Y",76.2,295,0))

    # ---- GPIO TABLE ----
    o.append(T("=== GPIO ASSIGNMENT (snes-hardware.md) ===", 220, 200, 3.81, True))
    o.append(T("Display: GPIO4-11=D0-D7, 12=CS, 13=RST, 14=DC, 46=WR, 3=RD, 45=BL", 220, 206))
    o.append(T("SD Card: GPIO36=MOSI, 37=MISO, 38=CLK, 39=CS", 220, 211))
    o.append(T("Audio:   GPIO15=BCLK, 16=LRCK, 17=DOUT", 220, 216))
    o.append(T("Buttons: 40=UP 41=DOWN 42=LEFT 1=RIGHT 2=A 48=B 47=X 21=Y", 220, 221))
    o.append(T("         18=START 0=SELECT 35=L 19=R", 220, 226))
    o.append(T("Joystick: 20=X_AXIS 44(RX0)=Y_AXIS", 220, 231))
    o.append(T("Reserved: GPIO26-32=PSRAM, GPIO43=TX0 debug", 220, 236))

    # ---- TITLE ----
    o.append(T("ESP32 Emu Turbo - Complete Electrical Schematic Rev 2.0", 25.4, 320, 3.81, True))
    o.append(T("Generated by scripts/generate-schematic.py | KiCad 9.0", 25.4, 326))

    o.append('\n  (sheet_instances (path "/" (page "1")))\n)\n')
    return ''.join(o)

if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "hardware", "kicad", "esp32-emu-turbo.kicad_sch")
    content = generate()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(content)
    print(f"Generated {out} ({content.count(chr(10))} lines)")
    print("Components: U1(ESP32-S3) U2(IP5306) U3(AMS1117) U4(ST7796S) U5(PAM8403) U6(SD) J1(USB-C) J2(Joystick) BT1 LS1 SW1-12 R1-15 C1-16")
