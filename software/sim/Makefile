# ESP32 Emu Turbo — Native Simulator Build
#
# Usage:
#   make          # Build simulator
#   make run      # Build + run
#   make clean    # Remove binaries

CC = gcc
CFLAGS = -DSIM_BUILD -Wall -O2 -Wno-unused-variable -Wno-unused-function
SDL_CFLAGS = $(shell sdl2-config --cflags)
SDL_LIBS = $(shell sdl2-config --libs)
LDFLAGS = $(SDL_LIBS) -lm

# Emulator cores from retro-go
COMP = ../components

# Nofrendo (NES)
NF_DIR = $(COMP)/nofrendo
NF_SRCS = $(NF_DIR)/nofrendo.c $(wildcard $(NF_DIR)/nes/*.c) $(wildcard $(NF_DIR)/mappers/*.c)

# Gnuboy (GB/GBC)
GB_DIR = $(COMP)/gnuboy
GB_SRCS = $(wildcard $(GB_DIR)/*.c)

# SMSPlus (SMS/GG)
SMS_DIR = $(COMP)/smsplus
SMS_SRCS = $(wildcard $(SMS_DIR)/*.c) $(wildcard $(SMS_DIR)/cpu/*.c) $(wildcard $(SMS_DIR)/sound/*.c)

# PCE-Go (PC Engine)
PCE_DIR = $(COMP)/pce-go
PCE_SRCS = $(wildcard $(PCE_DIR)/*.c)

# SNES9x excluded — too many portability issues for native macOS build.
# SNES uses stub core. Integration requires ESP-IDF component build.

CORE_INC = -I$(NF_DIR) -I$(NF_DIR)/nes -I$(GB_DIR) -I$(SMS_DIR) -I$(PCE_DIR)
CORE_SRCS = $(NF_SRCS) $(GB_SRCS) $(SMS_SRCS) $(PCE_SRCS)

SRCS = sim_main.c sim_hal.c sim_display.c sim_input.c sim_audio.c sim_sdcard.c \
       rom_check.c emu_core.c emu_nes.c emu_gb.c emu_sms.c emu_pce.c \
       $(CORE_SRCS)
CFLAGS += $(CORE_INC) -Wno-implicit-function-declaration
TARGET = emu-turbo-sim

.PHONY: all run clean test_all

all: $(TARGET)

TEST_SRCS = test_all_cores.c sim_hal.c sim_display.c sim_input.c sim_audio.c sim_sdcard.c \
            rom_check.c emu_core.c emu_nes.c emu_gb.c emu_sms.c emu_pce.c $(CORE_SRCS)

test_all: $(TEST_SRCS)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) -o test_all_cores $^ $(LDFLAGS)

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
