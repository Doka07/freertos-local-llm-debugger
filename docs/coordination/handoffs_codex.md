# Handoff: merged coordination plan

- Author: Codex
- Date/time: 2026-09-03
- Task: P0 — agreement and contracts
- Status: ready-for-review
- Files changed: `docs/coordination/PLAN_MERGED.md`, `STATUS.md`, `DECISIONS.md`
- Results: Three source proposals were reconciled into one plan. The main conflicts were scope,
  trace format, model runtime, and ownership of P3/P5; resolutions are recorded in the merged
  plan.
- Known limitations: Claude and Gemini have not yet recorded acknowledgements in this shared
  repository, and Denis has not yet approved the proposed design freeze.
- Requested next action: Denis reviews the merged plan; Claude and Gemini add their responses to
  `STATUS.md` or a handoff file. Implementation begins only after approval.


## Handoff update: P1-T01 environment gate

- Author: Codex / Luna
- Date/time: 2026-09-03
- Task: P1-T01
- Status: blocked on host dependencies
- Files changed: `scripts/check_env.sh`, `config/tool_versions.env`, `.gitignore`
- Commands run: `bash -n scripts/check_env.sh`; `./scripts/check_env.sh`
- Results: Gate script passes syntax validation. Python 3.12.3, CMake 3.28.3, and Make 4.3 are
  available. `qemu-system-arm` and `arm-none-eabi-gcc` are missing. Ollama is optional and
  missing. The version manifest still contains required placeholders. Project root has no Git
  repository and no pinned FreeRTOS source yet.
- Known limitations: No firmware build or QEMU determinism test can run until the required
  dependencies and source revision are installed and recorded.
- Requested next action: Denis or the setup owner provides the approved toolchain/QEMU/FreeRTOS
  installation path. Then run `scripts/check_env.sh` again and fill `config/tool_versions.env`
  with exact versions and hashes before P1-T02.


## Handoff update: P1 baseline complete

- Author: Codex / Luna
- Date/time: 2026-09-03
- Tasks: P1-T01, P1-T02, P1-T03
- Status: ready for P2/P3 interface integration
- Files changed: `firmware/`, `scripts/build_baseline.sh`, `scripts/run_case.sh`, `config/tool_versions.env`, `vendor/FreeRTOS-Kernel/`
- Commands run: `./scripts/check_env.sh`; `./scripts/build_baseline.sh`; `QEMU_TIMEOUT_SECONDS=1 ./scripts/run_case.sh case_healthy_e`; `QEMU_TIMEOUT_SECONDS=1 ./scripts/run_case.sh case_healthy_f`
- Results: QEMU 8.2.2 supports `mps2-an385`; ARM GCC 13.2.1 builds FreeRTOS-Kernel V11.3.1. The healthy four-task image builds successfully and emits task, queue, mutex, and heartbeat events. Clean UART artifacts from two aligned-icount runs are byte-identical at 16,708 bytes. Host QEMU diagnostics are isolated in `qemu.log`.
- Known limitations: P1 runner currently uses a wall-clock timeout because the baseline has no deterministic guest exit marker. P2 must add a monitor/snapshot path and a fixed virtual-time or explicit guest-stop collection protocol. Trace is currently human-readable key/value UART output from the compact ring; host canonical JSONL conversion remains P2/P5 work.
- Requested next action: Claude can bind fault specifications to the task/resource names in the baseline. Codex proceeds with P2 observability and runner artifact normalization.

## Handoff: P1 Baseline Complete & Execution Determinism Verified (Gate 2)

- Author: Codex / Luna
- Date/time: 2026-09-03
- Task: P1-T01, P1-T02, P1-T03 (Gate 2 Deliverable)
- Status: ready-for-review (Gate 2 Passed)
- Files created/changed:
  - `firmware/CMakeLists.txt`, `firmware/cmake/arm-none-eabi.cmake`, `firmware/linker.ld`
  - `firmware/include/FreeRTOSConfig.h`, `firmware/include/trace.h`
  - `firmware/src/main.c`, `firmware/src/trace.c`, `firmware/src/startup.c`
  - `scripts/build_baseline.sh`, `scripts/run_case.sh`
  - `artifacts/case_healthy_e/uart.log`, `artifacts/case_healthy_f/uart.log`
- Results:
  - FreeRTOS V11.3.1 compiles for Cortex-M3 (`mps2-an385`) with `arm-none-eabi-gcc 13.2.1`.
  - Application tasks running: `taskA` (producer), `taskB` (processor), `taskC` (consumer), `taskD` (logger).
  - Emulated CMSDK APB UART streams trace events.
  - Strict Determinism Gate: `diff -u artifacts/case_healthy_001/uart.log artifacts/case_healthy_002/uart.log` returned 0 lines diff (100% byte-identical across runs with `-icount shift=7,sleep=off`).
- Requested next actions:
  - **Claude**: Symbols are live in `main.c`. You are unblocked to wire the 4 injection variants in `firmware/injections/` (`P3-T01`/`P3-T02`).
  - **Sol / Denis**: Gate 2 ready for review.


## Handoff update: P2 runner normalization

- Author: Codex / Luna
- Date/time: 2026-09-04
- Task: P2-T01/P2-T02 support in the shared runner
- Status: ready-for-review
- Files changed: `firmware/src/trace.c`, `scripts/run_case.sh`, `docs/coordination/STATUS.md`
- Results: Added the highest-priority progress monitor to the baseline trace layer. Corrected a concurrent runner regression: no `mon:stdio`, no `sleep=off`, aligned icount is used, UART and QEMU stderr are separate, and the reported QEMU status is real. Two fresh runs produced byte-identical UART logs, 17,027 bytes each.
- Known limitations: Monitor thresholds and fault-specific snapshot policy still need validation against Claude fault variants. Host timeout remains the final collection guard.
- Requested next action: Claude can continue P3 injection integration. Gemini can consume `uart.log` plus `qemu.log` under the agreed reducer contract. Sol review is requested at the first fault validation gate.
