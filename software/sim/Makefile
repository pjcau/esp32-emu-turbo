# ESP32 Emu Turbo — Native Simulator Build
#
# Usage:
#   make          # Build simulator
#   make run      # Build + run
#   make clean    # Remove binaries

CC = gcc
CFLAGS = -DSIM_BUILD -Wall -O2
SDL_CFLAGS = $(shell sdl2-config --cflags)
SDL_LIBS = $(shell sdl2-config --libs)
LDFLAGS = $(SDL_LIBS) -lm

SRCS = sim_main.c sim_hal.c sim_display.c sim_input.c sim_audio.c sim_sdcard.c rom_check.c emu_core.c
TARGET = emu-turbo-sim

.PHONY: all run clean

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) -o $@ $^ $(LDFLAGS)

run: $(TARGET)
	@echo ""
	@echo "ESP32 Emu Turbo — Simulator"
	@echo "==========================="
	@echo "  D-pad:   W/A/S/D     L/R:     Q/E"
	@echo "  A/B:     J/K         Start:   Enter"
	@echo "  X/Y:     U/I         Select:  Backspace"
	@echo "  Power:   P           Quit:    ESC"
	@echo ""
	./$(TARGET) ../../test-roms

clean:
	rm -f $(TARGET) sim_test sim_test_native
