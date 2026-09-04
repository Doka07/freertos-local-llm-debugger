#!/usr/bin/env bash
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
build_dir="${BUILD_DIR:-$repo_root/build/baseline-arm}"

cmake -S "$repo_root/firmware" -B "$build_dir" \
    -DCMAKE_TOOLCHAIN_FILE="$repo_root/firmware/cmake/arm-none-eabi.cmake" \
    -DCMAKE_BUILD_TYPE=Debug \
    -DFAULT_CASE="${FAULT_CASE:-}"
cmake --build "$build_dir" --parallel
echo "ELF: $build_dir/freertos_baseline.elf"
