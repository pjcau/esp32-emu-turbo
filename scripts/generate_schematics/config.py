"""Shared configuration: GPIO mapping, ESP32 pin definitions, layout constants."""

# --- GPIO mapping (source of truth: website/docs/snes-hardware.md) ---
GPIO_NETS: dict[int, str] = {
    4: "LCD_D0", 5: "LCD_D1", 6: "LCD_D2", 7: "LCD_D3",
    8: "LCD_D4", 9: "LCD_D5", 10: "LCD_D6", 11: "LCD_D7",
    12: "LCD_CS", 13: "LCD_RST", 14: "LCD_DC", 46: "LCD_WR",
    3: "LCD_RD", 45: "LCD_BL",
    36: "SD_MOSI", 37: "SD_MISO", 38: "SD_CLK", 39: "SD_CS",
    15: "I2S_BCLK", 16: "I2S_LRCK", 17: "I2S_DOUT",
    40: "BTN_UP", 41: "BTN_DOWN", 42: "BTN_LEFT", 1: "BTN_RIGHT",
    2: "BTN_A", 48: "BTN_B", 47: "BTN_X", 21: "BTN_Y",
    18: "BTN_START", 0: "BTN_SELECT", 35: "BTN_L", 19: "BTN_R",
    20: "JOY_X", 44: "JOY_Y",
}

# ESP32-S3 pin# -> (side, gpio#_or_name, y_offset_from_center)
# side: L=left, R=right, B=bottom
ESP_PINS: dict[int, tuple] = {
    1: ("L", "3V3", 38.1), 2: ("L", "3V3", 35.56), 3: ("L", "EN", 33.02),
    4: ("L", 4, 30.48), 5: ("L", 5, 27.94), 6: ("L", 6, 25.4), 7: ("L", 7, 22.86),
    8: ("L", 15, 20.32), 9: ("L", 16, 17.78), 10: ("L", 17, 15.24), 11: ("L", 18, 12.7),
    12: ("L", 8, 10.16), 13: ("L", 19, 5.08), 14: ("L", 20, 2.54), 15: ("L", 3, 0),
    16: ("L", 46, -5.08), 17: ("L", 9, -7.62), 18: ("L", 10, -10.16), 19: ("L", 11, -12.7),
    20: ("R", 12, 38.1), 21: ("R", 13, 35.56), 22: ("R", 14, 33.02), 23: ("R", 21, 30.48),
    24: ("R", 47, 27.94), 25: ("R", 48, 25.4), 26: ("R", 45, 22.86), 27: ("R", 0, 20.32),
    28: ("R", 35, 17.78), 29: ("R", 36, 15.24), 30: ("R", 37, 12.7), 31: ("R", 38, 10.16),
    32: ("R", 39, 7.62), 33: ("R", 40, 5.08), 34: ("R", 41, 2.54), 35: ("R", 42, 0),
    36: ("R", "TX0", -5.08), 37: ("R", "RX0", -7.62), 38: ("R", 1, -10.16), 39: ("R", 2, -12.7),
    40: ("B", "GND", 0), 41: ("B", "GND", 2.54),
}

# Net groups for cross-sheet labels
DISPLAY_NETS = [
    "LCD_D0", "LCD_D1", "LCD_D2", "LCD_D3",
    "LCD_D4", "LCD_D5", "LCD_D6", "LCD_D7",
    "LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR", "LCD_RD", "LCD_BL",
]
AUDIO_NETS = ["I2S_BCLK", "I2S_LRCK", "I2S_DOUT"]
SD_NETS = ["SD_MOSI", "SD_MISO", "SD_CLK", "SD_CS"]
BUTTON_NETS = [
    "BTN_UP", "BTN_DOWN", "BTN_LEFT", "BTN_RIGHT",
    "BTN_A", "BTN_B", "BTN_X", "BTN_Y",
    "BTN_START", "BTN_SELECT", "BTN_L", "BTN_R",
]
JOYSTICK_NETS = ["JOY_X", "JOY_Y"]


def _get_sheet_defs():
    """Lazy import to avoid circular imports."""
    from .sheets.power_supply import PowerSupplySheet
    from .sheets.mcu import MCUSheet
    from .sheets.display import DisplaySheet
    from .sheets.audio import AudioSheet
    from .sheets.sd_card import SDCardSheet
    from .sheets.controls import ControlsSheet
    from .sheets.joystick import JoystickSheet

    return [
        {"filename": "01-power-supply.kicad_sch", "module": PowerSupplySheet},
        {"filename": "02-mcu.kicad_sch", "module": MCUSheet},
        {"filename": "03-display.kicad_sch", "module": DisplaySheet},
        {"filename": "04-audio.kicad_sch", "module": AudioSheet},
        {"filename": "05-sd-card.kicad_sch", "module": SDCardSheet},
        {"filename": "06-controls.kicad_sch", "module": ControlsSheet},
        {"filename": "07-joystick.kicad_sch", "module": JoystickSheet},
    ]


# Will be populated on first access
SHEET_DEFS: list[dict] = []


def _init():
    global SHEET_DEFS
    SHEET_DEFS = _get_sheet_defs()
