/**
 * Input driver — SDL2 simulator implementation
 * 12 SNES buttons + power switch, all via keyboard
 */

#ifdef SIM_BUILD

#include "sim_hal.h"
#include <stdio.h>

static int g_power_on = 1;  /* power switch state */

int input_sim_init(void) {
    printf("[INPUT] 12 buttons + power switch initialized (keyboard)\n");
    printf("[INPUT] D-pad: WASD | AB: JK | XY: UI | Start: Enter | Select: Backspace | LR: QE | Power: P\n");
    return 0;
}

uint16_t input_sim_read(void) {
    return sim_buttons_read();
}

int input_sim_power_switch(void) {
    return g_power_on;
}

void input_sim_toggle_power(void) {
    g_power_on = !g_power_on;
    printf("[INPUT] Power switch: %s\n", g_power_on ? "ON" : "OFF");
}

const char *input_sim_button_name(int bit) {
    static const char *names[] = {
        "UP", "DOWN", "LEFT", "RIGHT",
        "A", "B", "X", "Y",
        "START", "SELECT", "L", "R"
    };
    if (bit >= 0 && bit < 12) return names[bit];
    return "?";
}

#endif
