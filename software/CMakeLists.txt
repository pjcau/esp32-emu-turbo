cmake_minimum_required(VERSION 3.16)

# Restrict the ESP-IDF build to the hardware-validation firmware (main and
# its dependencies). The emulator cores under components/ (snes9x, nofrendo,
# gnuboy, gwenesis, pce-go, smsplus) declare COMPONENT_REQUIRES "retro-go",
# a base component this repo does not vendor — they are compiled by the SDL
# simulator's own build (software/sim), not by ESP-IDF, and have never built
# here. Listing them without their dependency would fail configuration, and
# silently vendoring retro-go is a porting task, not a build flag.
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32-emu-turbo)
