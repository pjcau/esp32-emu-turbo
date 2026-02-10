"""KiCad library symbol definitions for all components."""

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
        (pin power_in line (at 2.54 -41.91 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "41" (effects (font (size 1.016 1.016)))))))\n"""

_SYMBOL_AMS1117 = """    (symbol "AMS1117-3.3" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "U" (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (property "Value" "AMS1117-3.3" (at 0 -5.08 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "AMS1117-3.3_0_1" (rectangle (start -5.08 3.81) (end 5.08 -3.81) (stroke (width 0.254) (type default)) (fill (type background))))
      (symbol "AMS1117-3.3_1_1"
        (pin power_in line (at -7.62 2.54 0) (length 2.54) (name "VIN" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin power_in line (at 0 -6.35 90) (length 2.54) (name "GND" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin power_out line (at 7.62 2.54 180) (length 2.54) (name "VOUT" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))))\n"""

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

_SYMBOL_IP5306 = """    (symbol "IP5306_Module" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
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
        (pin power_out line (at 10.16 -3.81 180) (length 2.54) (name "OUT_5V" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))))\n"""

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
        (pin output line (at 10.16 0 180) (length 2.54) (name "SPK-" (effects (font (size 1.016 1.016)))) (number "5" (effects (font (size 1.016 1.016)))))))\n"""

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
        (pin passive line (at -3.81 0.635 0) (length 2.54) (name "+" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at -3.81 -0.635 0) (length 2.54) (name "-" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))))\n"""

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

_SYMBOL_GND = """    (symbol "GND" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -5.08 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "GND" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) (xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_3V3 = """    (symbol "+3V3" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+3V3" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+3V3_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+3V3_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+3V3" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

_SYMBOL_5V = """    (symbol "+5V" (pin_names (offset 0) hide) (in_bom no) (on_board no)
      (property "Reference" "#PWR" (at 0 -3.81 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+5V" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
      (symbol "+5V_0_1"
        (polyline (pts (xy -0.762 1.27) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 2.54)) (stroke (width 0) (type default)) (fill (type none)))
        (polyline (pts (xy 0 2.54) (xy 0.762 1.27)) (stroke (width 0) (type default)) (fill (type none))))
      (symbol "+5V_1_1" (pin power_in line (at 0 0 90) (length 0) (name "+5V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))))\n"""

# Registry: symbol name -> definition string
SYMBOLS: dict[str, str] = {
    "ESP32-S3-WROOM-1": _SYMBOL_ESP32,
    "AMS1117-3.3": _SYMBOL_AMS1117,
    "C": _SYMBOL_C,
    "R": _SYMBOL_R,
    "SW_Push": _SYMBOL_SW_PUSH,
    "IP5306_Module": _SYMBOL_IP5306,
    "PAM8403_Module": _SYMBOL_PAM8403,
    "SD_Module": _SYMBOL_SD,
    "ST7796S_Module": _SYMBOL_ST7796S,
    "Battery": _SYMBOL_BATTERY,
    "USB_C": _SYMBOL_USB_C,
    "Speaker": _SYMBOL_SPEAKER,
    "PSP_Joystick": _SYMBOL_JOYSTICK,
    "PWR_FLAG": _SYMBOL_PWR_FLAG,
    "GND": _SYMBOL_GND,
    "+3V3": _SYMBOL_3V3,
    "+5V": _SYMBOL_5V,
}


def lib_symbols_block(needed: list[str]) -> str:
    """Return (lib_symbols ...) block with only the needed symbol defs."""
    parts = ["  (lib_symbols\n"]
    # Always include power symbols
    always = {"GND", "+3V3", "+5V"}
    for name in list(needed) + sorted(always - set(needed)):
        if name in SYMBOLS:
            parts.append(SYMBOLS[name])
    parts.append("  )\n")
    return "".join(parts)
