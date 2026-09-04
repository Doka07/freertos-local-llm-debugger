cmake_minimum_required(VERSION 3.20)
project(freertos_baseline C ASM)

set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(FREERTOS_DIR ${CMAKE_CURRENT_LIST_DIR}/../vendor/FreeRTOS-Kernel)
set(FREERTOS_PORT ${FREERTOS_DIR}/portable/GCC/ARM_CM3)

set(TARGET_SRC src/main.c)
if(DEFINED FAULT_CASE AND EXISTS "${CMAKE_CURRENT_LIST_DIR}/injections/${FAULT_CASE}.c")
    set(TARGET_SRC injections/${FAULT_CASE}.c)
    message(STATUS "Building fault variant: ${FAULT_CASE}")
endif()

add_executable(freertos_baseline
    ${TARGET_SRC}
    src/startup.c
    src/trace.c
    ${FREERTOS_DIR}/list.c
    ${FREERTOS_DIR}/queue.c
    ${FREERTOS_DIR}/tasks.c
    ${FREERTOS_DIR}/timers.c
    ${FREERTOS_DIR}/event_groups.c
    ${FREERTOS_DIR}/stream_buffer.c
    ${FREERTOS_DIR}/portable/MemMang/heap_4.c
    ${FREERTOS_PORT}/port.c
)

target_include_directories(freertos_baseline PRIVATE
    ${CMAKE_CURRENT_LIST_DIR}/include
    ${FREERTOS_DIR}/include
    ${FREERTOS_PORT}
)

target_compile_options(freertos_baseline PRIVATE
    -mcpu=cortex-m3 -mthumb -mfloat-abi=soft
    -ffreestanding -fdata-sections -ffunction-sections
    -Wall -Wextra -Wno-unused-parameter
)

target_link_options(freertos_baseline PRIVATE
    -mcpu=cortex-m3 -mthumb -mfloat-abi=soft
    -T${CMAKE_CURRENT_LIST_DIR}/linker.ld
    -Wl,--gc-sections -Wl,-Map=${CMAKE_CURRENT_BINARY_DIR}/freertos_baseline.map
)

set_target_properties(freertos_baseline PROPERTIES
    SUFFIX ".elf"
)

add_custom_command(TARGET freertos_baseline POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:freertos_baseline>
            ${CMAKE_CURRENT_BINARY_DIR}/freertos_baseline.bin
    COMMAND ${CMAKE_SIZE} $<TARGET_FILE:freertos_baseline>
)
