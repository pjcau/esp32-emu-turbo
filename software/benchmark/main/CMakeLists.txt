set(CORE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../../components")

# Collect all emulator core sources
file(GLOB NF_SRCS  "${CORE_DIR}/nofrendo/*.c" "${CORE_DIR}/nofrendo/nes/*.c" "${CORE_DIR}/nofrendo/mappers/*.c")
file(GLOB GB_SRCS  "${CORE_DIR}/gnuboy/*.c")
file(GLOB SMS_SRCS "${CORE_DIR}/smsplus/*.c" "${CORE_DIR}/smsplus/cpu/*.c" "${CORE_DIR}/smsplus/sound/*.c")
file(GLOB PCE_SRCS "${CORE_DIR}/pce-go/*.c")
file(GLOB SNES_SRCS "${CORE_DIR}/snes9x/src/*.c")
list(FILTER SNES_SRCS EXCLUDE REGEX "snapshot\\.c$")

idf_component_register(
    SRCS
        "bench_main.c"
        "bench_nes.c"
        "bench_gb.c"
        "bench_sms.c"
        "bench_pce.c"
        "bench_snes.c"
        "qemu_display.c"
        ${NF_SRCS}
        ${GB_SRCS}
        ${SMS_SRCS}
        ${PCE_SRCS}
        ${SNES_SRCS}
    INCLUDE_DIRS
        "."
        "${CORE_DIR}/nofrendo"
        "${CORE_DIR}/nofrendo/nes"
        "${CORE_DIR}/nofrendo/mappers"
        "${CORE_DIR}/gnuboy"
        "${CORE_DIR}/smsplus"
        "${CORE_DIR}/smsplus/cpu"
        "${CORE_DIR}/smsplus/sound"
        "${CORE_DIR}/pce-go"
        "${CORE_DIR}/snes9x/src"
    REQUIRES
        esp_timer
        spiffs
        esp_partition
        esp_lcd
        driver
    EMBED_FILES
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/owlia.nes"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/blarggs-cpu-instrs.gb"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/ucity.gbc"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/silvervalley.sms"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/Swabby-GG-1.11.gg"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/reflectron.pce"
        "${CMAKE_CURRENT_SOURCE_DIR}/../spiffs_data/superbossgaiden.sfc"
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE BENCH_BUILD NO_ZERO_LUT)
target_compile_options(${COMPONENT_LIB} PRIVATE
    -O2 -Wno-unused-variable -Wno-unused-function
    -Wno-implicit-function-declaration -Wno-sequence-point
    -Wno-maybe-uninitialized -Wno-format -Wno-error
)
