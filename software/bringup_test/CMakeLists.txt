cmake_minimum_required(VERSION 3.16)

# Bring-up test firmware — a separate ESP-IDF project from the application in
# software/, so validating a board never means editing (or restoring) main.c.
# It compiles the *production* drivers out of software/main, because a
# validation firmware that configures a peripheral differently from the
# shipping firmware validates something the shipping firmware never does.
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(esp32-emu-turbo-bringup)
