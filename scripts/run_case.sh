#!/usr/bin/env bash
set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
case_id="${1:-case_healthy_001}"
build_dir="${BUILD_DIR:-$repo_root/build/baseline-arm}"
artifact_dir="$repo_root/artifacts/$case_id"

FAULT_CASE="$case_id" "$repo_root/scripts/build_baseline.sh" >/dev/null
mkdir -p "$artifact_dir"
timeout_seconds="${QEMU_TIMEOUT_SECONDS:-2}"

exit_status="$(python3 - "$build_dir/freertos_baseline.elf" "$artifact_dir/uart.log" "$timeout_seconds" << 'PYEOF'
import sys, subprocess, time, pathlib

elf_path = sys.argv[1]
log_path = pathlib.Path(sys.argv[2])
qemu_log_path = log_path.with_name("qemu.log")
timeout_s = float(sys.argv[3])

proc = subprocess.Popen(
    ["qemu-system-arm", "-machine", "mps2-an385", "-kernel", elf_path, "-nographic", "-icount", "shift=7,align=on"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
time.sleep(timeout_s)
proc.terminate()
stdout, stderr = proc.communicate()
qemu_log_path.write_text(stderr)
log_path.write_text(stdout)
print(proc.returncode)
PYEOF
)"

printf '{"case_id":"%s","qemu_exit_status":%s,"artifact":"%s/uart.log"}\n' \
    "$case_id" "${exit_status:-1}" "$artifact_dir"
exit 0
