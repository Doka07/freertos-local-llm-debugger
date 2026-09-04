## Handoff: P3 fault specifications and private-label format (draft)

- Author: Claude
- Date/time: 2026-09-03
- Based on: `PLAN_MERGED.md` (design freeze proposal, §2–§6), acknowledged in §9
- Task: P3 — Fault laboratory
- Status: proposed (drafting in parallel with Denis's approval / Gemini's schema work per
  Codex's request in `handoffs_codex.md`; not blocking, will revise if the design freeze
  changes)
- Files changed: this file only. No firmware or schema files created yet — P1 baseline
  doesn't exist, so nothing here is committed as an interface until Codex's skeleton lands.

### Scope

The four core v1 classes from `PLAN_MERGED.md` §2, plus the mandatory healthy control. Task
set follows the baseline concept already agreed across all three source plans: `taskA`
(producer), `taskB` (processor), `taskC` (comms/consumer), `taskD` (logger), shared `mtx1`,
`mtx2`, `q1`, `sem1`. All four fault classes reuse these same names — the only difference
between a fault variant and the healthy control is the injected defect, never the identifiers.

### Private label schema (`labels/<case_id>.json`)

Field names mirror the agreed verdict shape in `PLAN_MERGED.md` §5 so the scorer can diff
`verdict.json` against `labels/<case_id>.json` directly, field by field:

```json
{
  "schema_version": "1.0",
  "case_id": "case_001",
  "is_fault": true,
  "failure_class": "DEADLOCK_LOCK_ORDER",
  "culprit_tasks": ["taskA", "taskB"],
  "culprit_objects": ["mtx1", "mtx2"],
  "expected_evidence": [
    "taskA holds mtx1 and is BLOCKED on mtx2",
    "taskB holds mtx2 and is BLOCKED on mtx1",
    "no forward progress after ts=T on either task"
  ],
  "primary_mechanism": "private, human-readable, never enters the evidence pack",
  "injection_source": "private/path, stripped by the reducer's allowlist"
}
```

Healthy control: `is_fault: false`, `failure_class: "NONE"`, `culprit_tasks: []`,
`culprit_objects: []`.

`failure_class` enum for v1 (versioned; extending this list is a `DECISIONS.md` entry, not a
silent edit): `DEADLOCK_LOCK_ORDER`, `PRIORITY_INVERSION`, `MISSED_ISR_NOTIFICATION`,
`MISSING_MUTEX_RELEASE`, `NONE`.

### Class 1 — `DEADLOCK_LOCK_ORDER`

- Setup: `taskA` (prio 2) takes `mtx1`, delays briefly, then requests `mtx2`. `taskB` (prio 2)
  takes `mtx2`, delays briefly, then requests `mtx1`.
- Expected trace signature (neutral, no class name in it): `MTX_TAKE mtx1 owner=taskA OK`,
  `MTX_TAKE mtx2 owner=taskB OK`, `MTX_TAKE mtx2 task=taskA RET=BLOCK`,
  `MTX_TAKE mtx1 task=taskB RET=BLOCK`, then no `CTX_SWITCH` progress on either task —
  watchdog fires and dumps the snapshot.
- Distinguishing evidence vs. class 4 (missing release): this is a **cycle** — two tasks each
  hold one resource the other needs. Class 4 has exactly one task holding, one task blocked,
  and no cycle.
- Healthy reference: same two tasks, both acquire `mtx1` then `mtx2` in the same order —
  no simultaneous cross-hold is ever possible.

### Class 2 — `PRIORITY_INVERSION`

- Setup: `taskD`→relabel as `taskLow` role at prio 1 takes a shared resource guarding
  telemetry; `taskC`→`taskHigh` role at prio 3 blocks waiting for it; `taskB`→`taskMed` role
  at prio 2 is CPU-bound and preempts the low-priority holder while it owns the resource.
  (Keeping the generic `taskA..D` names in the actual trace — role mapping is documented here
  only for spec clarity, never in evidence.)
- Fault mechanism: the shared resource is created with `xSemaphoreCreateBinary()` instead of
  `xSemaphoreCreateMutex()` — identical call sites, so the only diff is which constructor ran.
  No inheritance, so `taskMed` can starve the holder indefinitely.
- Healthy/reference variant: same three tasks, same timing, resource created with
  `xSemaphoreCreateMutex()` and `configUSE_MUTEXES == 1` — priority inheritance boosts the
  holder's effective priority while held, so `taskMed` cannot fully starve it. This reference
  run is what lets the model (and the write-up) distinguish real inversion from ordinary
  blocking, per `PLAN_MERGED.md` §4 P3 exit gate.
- Evidence: in the fault case, `taskHigh` stays `BLOCKED` on the resource for a duration much
  longer than the holder's own critical-section length, while the trace shows `taskMed`
  running at its own priority (not elevated) throughout; the holder's `P:` field never changes
  from its base priority. In the reference case the holder's effective priority in the trace
  rises to `taskHigh`'s level for the hold duration.

### Class 3 — `MISSED_ISR_NOTIFICATION`

- Setup: a periodic timer ISR is meant to notify a consumer task (`xTaskNotifyFromISR` or
  ISR-safe queue send) on each period. The consumer waits on that notification in a loop and
  processes it.
- Fault mechanism: the ISR calls a non-ISR-safe blocking API (e.g. `xQueueSend` instead of
  `xQueueSendFromISR`, or a notify with `eSetValueWithoutOverwrite` racing a slow consumer) so
  a fraction (or all, depending on variant) of notifications never reach the consumer.
- Expected trace signature: periodic `EVT=ISR_FIRE` or equivalent entries continue at a steady
  rate; the consumer's `EVT=NOTIFY_WAIT`/`Q_RECV` entries stop advancing — its progress
  counter stalls while the ISR's counter keeps incrementing. No error/assert necessarily
  fires; the evidence is the divergence between the two counters, not an explicit failure
  event — this is deliberate, it is the hardest class to leak the answer for.
- Distinguishing evidence vs. class 1/4: no mutex ownership involved at all; the consumer is
  `BLOCKED` on a queue/notification with no owner, not on another task's held resource.
- Healthy reference: identical ISR and consumer, correct `FromISR` API — counters track
  together within a small bounded skew.

### Class 4 — `MISSING_MUTEX_RELEASE`

- Setup: `taskA` takes `mtx1`, then follows an error path (e.g. a simulated sensor-read
  failure) that returns early without calling the corresponding give.
- Expected trace signature: exactly one `MTX_TAKE mtx1 owner=taskA OK`, no matching
  `MTX_GIVE mtx1` ever, followed later by `MTX_TAKE mtx1 task=taskB RET=BLOCK` that never
  resolves. `taskA` itself continues running or goes idle — it is not itself blocked on
  anything.
- Distinguishing evidence vs. class 1: single resource, single permanently-blocked task, no
  cycle. The absence of a `MTX_GIVE` event for the only `MTX_TAKE` on that resource is the
  key signal the reducer must preserve (it must not silently drop "boring" un-matched takes).
- Healthy reference: same error-path structure, but the path releases the mutex before
  returning (e.g. via a cleanup/`goto` release or RAII-style pattern) — trace shows the
  matching `MTX_GIVE`.

### Open items for Codex/Gemini before these become committed interfaces

1. Confirms whether `PRIORITY_INVERSION`'s reference run ships in v1 core or is deferred —
   `PLAN_MERGED.md` §4 says "where technically meaningful," I'm treating it as required
   because without it the class isn't falsifiable as *inversion* vs. ordinary blocking.
2. Reducer must guarantee un-matched `MTX_TAKE` (no later `MTX_GIVE` for that owner/resource
   pair) survives token-budget trimming — otherwise class 4's only signal can get cut.
3. Watchdog stall threshold needs to be long enough that class 2's `taskMed` interference
   window doesn't itself trip the "no progress" detector on the healthy reference run.

### Requested next action

Codex: once the P1 baseline skeleton exists, confirm task/resource names above match what's
actually wired in `main.c`, and flag if `q1`/`sem1` end up unused (class 3 may use a queue or
a notification depending on what's easiest to fault reliably in QEMU — I've left both
plausible per `PLAN_MERGED.md`'s "if QEMU exposes it reliably" caveat from the earlier Codex
draft).

Gemini: confirm the label schema field names above line up with whatever `verdict.json`
enforcement you implement, so the scorer needs zero translation layer between the two.

---

## Handoff addendum: P3-T01 injection mechanism (design-ready, implementation blocked)

- Author: Claude
- Date/time: 2026-09-03
- Status: proposed — ready to implement the moment P1-T01 lands

`firmware/` does not exist on disk yet, so the four fault variants (each a compile-time
mutation of the P1 baseline's `main.c`/`tasks.c`) can't be written for real. Design is ready:

- One build flag, `-DFAULT_CASE=<enum>`, `NONE` by default (healthy control).
- `firmware/injections/` holds one `.c` per class (`deadlock_lock_order.c`,
  `priority_inversion.c`, `missed_isr_notification.c`, `missing_mutex_release.c`), each
  providing the same task-entry symbols the baseline uses so `main.c` doesn't branch on the
  fault case — the linker picks the variant, not an `#ifdef` ladder in shared code (keeps
  `main.c` itself un-mutated across variants, which matters for blinding: no case-specific
  branches for the model to ever see if source is ever included in an ablation run).
- `labels/<case_id>.json` is authored in lockstep with each variant, same commit, by me only.

Requested next action: ping me the moment `P1-T01` (baseline `main.c` + task/resource
scaffolding) is on disk — I'll wire the four variants against the real symbol names within
that session.

---

## Handoff addendum 2: fault-spec revisions per Sol's review (SOL-F01, SOL-F02, SOL-F03)

- Author: Claude
- Date/time: 2026-09-03
- Status: revised spec, still blocked on P1-T01 for actual source
- Based on: `REVIEW_SOL.md`

Sol's embedded-correctness findings are correct and I'm folding them into the spec now.

### SOL-F01 — deterministic ordering, not tick-delay ordering

Both Class 1 and Class 2 previously used "brief delay" to arrange lock-acquisition order.
That's flaky by construction — scheduler jitter, not a barrier, was doing the ordering work.

- **Class 1 (`DEADLOCK_LOCK_ORDER`):** add a startup barrier — each task takes its *first*
  mutex, then signals a shared ready-counter (e.g. gives a counting semaphore initialized to
  0, target count 2). Neither task requests its *second* mutex until the counter reaches 2.
  This guarantees both tasks provably hold their first mutex before the cross-request happens,
  independent of scheduler timing. Delay values become workload-realism parameters only,
  never the mechanism proving the ordering.
- **Class 2 (`PRIORITY_INVERSION`):** same idea, applied to force
  low-holder → high-waiter → medium-runner ordering: `taskHigh` and `taskMed` block on a
  startup gate that only releases after `taskLow` has confirmed (via the same
  counter/semaphore pattern) that it already holds the shared resource.
- **Class 2, semaphore initial state:** the binary semaphore fault variant must explicitly
  `xSemaphoreGive()` once immediately after `xSemaphoreCreateBinary()` — unlike a mutex (created
  unlocked by default), a binary semaphore is created *empty*. Forgetting this doesn't produce
  inversion, it produces an immediate, permanent, uninteresting block on the first take. This
  is exactly the kind of "confident but wrong" firmware bug the reducer should not confuse with
  the intended fault class, so it needs to be caught in review before it ships as a variant.
- **Class 2, priority capture:** the evidence pack's task table must carry both base priority
  and current/effective priority per task, not just one number. Effective priority is what
  proves (or disproves) that inheritance happened during the hold — without it, the healthy
  reference run and the fault run produce visually identical trace shapes for this field, which
  defeats the entire point of the reference run.

### SOL-F02 — single deterministic mechanism for Class 3, not two conflated bugs

My original spec described Class 3 as either "ISR calls a non-ISR-safe API" *or* "a
notify-overwrite race," picked per variant. Sol is right that these are materially different
failure modes: a non-ISR-safe call from interrupt context can assert or corrupt kernel state
outright, which doesn't reliably model a *silently* missed notification — it models a crash,
which is a different (and separately interesting, but not this-class) bug.

**Revised Class 3 — `MISSED_ISR_NOTIFICATION`:**
- Timer ISR fires every period, every time, and increments its own neutral progress counter
  regardless of fault/healthy build — the ISR itself is never broken.
- In the fault build, the ISR's call to `xTaskNotifyFromISR()` is deterministically omitted in
  the injected branch (compile-time, not racy) — e.g. the notify call is simply absent from the
  fault variant's ISR body, full stop, rather than conditionally skipped based on timing.
- Consumer task blocks on the notification and never wakes past that point.
- Expected trace: ISR progress counter increments steadily forever; consumer's
  `NOTIFY_WAIT`/progress counter stalls permanently after its last successful wake. Clean,
  reproducible counter divergence — no assert, no corruption, no race.
- The non-ISR-safe-API variant and the overwrite-race variant both move to the Phase-2/future
  class list, separately labelled, not folded into core v1's `MISSED_ISR_NOTIFICATION`.

### SOL-F03 — watchdog cannot be idle-hook-based (cross-cutting, flagging for Codex/P2)

In Class 2, `taskMed` is CPU-bound and higher priority than idle — while it's interfering with
`taskLow`, the idle task may never run at all, so an idle-hook watchdog would never fire during
the exact scenario it exists to catch. This isn't my owned path (`P2` observability is Codex's),
but it directly affects whether Class 2 is even collectible, so noting it here explicitly:
progress detection needs a small dedicated highest-priority monitor task woken periodically by
the tick hook to inspect per-task progress counters, plus a host-side QEMU timeout as the final
collection guard — not `vApplicationIdleHook`. Requesting Codex confirm this lands in P2-T02.

### Requested next action

Still: ping me when P1-T01's baseline interfaces (task/resource symbol names) exist. This
revision is otherwise ready to implement as-is.

---

## Handoff: P3-T01/T02 — firmware/injections/ implemented, compiled, and QEMU-validated

- Author: Claude
- Date/time: 2026-09-03
- Status: ready-for-review (3 of 4 core classes + 1 reference variant; class 3 blocked, see below)
- Files added: `firmware/injections/case_001_deadlock.c`, `case_002_priority_inversion.c`,
  `case_002r_priority_inheritance_reference.c`, `case_004_missing_release.c`,
  `labels/case_001_deadlock.json`, `case_002_priority_inversion.json`,
  `case_004_missing_release.json`, `case_005_healthy.json`
- Commands run: manual `arm-none-eabi-gcc`/`arm-none-eabi-ld` builds mirroring
  `firmware/CMakeLists.txt`'s flags (not yet wired into CMake itself — see request below),
  then `qemu-system-arm -machine mps2-an385 -kernel ... -icount shift=7,sleep=off` for each.
  All four link cleanly against `vendor/FreeRTOS-Kernel` + `firmware/src/{startup,trace}.c`
  with zero `-Wall -Wextra` warnings.

### Results, with real trace output

- **case_001 (deadlock):** taskA takes mtx1, taskB takes mtx2 (both OK), both then attempt
  their cross-mutex and neither ever succeeds — total silence from taskA/taskB after that,
  bystanders (taskC/taskD) keep running. Matches `labels/case_001_deadlock.json` exactly.
- **case_002 (priority inversion, fault):** taskD holds sem1 (binary semaphore) at ts=0;
  taskC (highest priority) blocks on it until ts=6262 — roughly 6.2k ticks, driven entirely by
  taskB's bounded CPU-bound interference.
- **case_002r (reference, real mutex):** same scenario, taskC blocks only ts=0→2 — two ticks.
  This is the side-by-side proof the inversion in case_002 is real, not just ordinary blocking.
- **case_004 (missing release):** taskA takes mtx1 once, never gives it back, keeps running
  normally forever after; taskB attempts and never succeeds. Single unmatched take, no cycle.

### A live edit conflict I found and fixed, with evidence

While validating, `case_001_deadlock.c` and `case_004_missing_release.c` were edited on disk
(not by me) to move the `trace_emit(TRACE_MUTEX_TAKE, ...)` call to *before* the
`xSemaphoreTake()` calls that are supposed to block forever. I understand the goal — without
a P2 monitor/watchdog yet, those permanently-blocked attempts otherwise leave *zero* trace
evidence at all, just silence. But the implementation reused the same event type as a genuine
success, with no status field to distinguish them (`trace_event_t` has no `ret`/status field),
so it was emitting a factually false "taskA took mtx2" event for an acquisition that never
happens. I re-tested the as-edited version and confirmed this: a real `type=6` (TAKE-success)
line appears for an operation that then blocks forever.

Fixed by applying the pattern I'd already used in `case_002`'s `taskC_high` (a `TRACE_TASK_RUN`
pre-marker before the blocking call, with `TRACE_MUTEX_TAKE` reserved strictly for confirmed
success) — no `trace.h` changes needed. Re-built and re-ran both cases; output now shows
exactly the pre-attempt marker plus permanent silence, never a false success line (see trace
excerpts above). Not reverting to the pre-edit version — the goal of getting *some* trace
evidence for the blocked attempt was right, just needed the right event type.

### Diagnosed: the empty `artifacts/case_healthy_001/uart.log` is not a systemic issue

I was worried the UART/QEMU pipeline itself was broken (P1's healthy run produced 0 bytes of
output). It isn't — my from-scratch builds against the identical `startup.c`/`trace.c`/
`linker.ld` produce full trace output immediately (boot line included) every time. Whatever
produced that empty artifact was specific to that one run/build, not the infrastructure.
Worth a rerun on Codex's side, but not something for me to chase further.

### Requests

1. **CMake wiring** — these four are currently only manually compiled, not build-system
   targets. Requesting Codex add one `add_executable(freertos_case_NAME ...)` per file in
   `firmware/CMakeLists.txt`, reusing every source/flag/link option the baseline target already
   uses except swapping `src/main.c` for the injection file. Happy to propose the exact CMake
   diff if that's easier than writing it from this description.
2. **Class 3 (`MISSED_ISR_NOTIFICATION`) is blocked on real infrastructure, not just my time.**
   `firmware/src/startup.c`'s vector table only covers the 16 standard Cortex-M system
   exceptions (through SysTick) — there are no IRQ (external interrupt) entries at all, so
   there is currently no way to wire up a real hardware timer interrupt for this class. I could
   fake it with a FreeRTOS software timer (`configUSE_TIMERS` is already on), but that runs in
   the Timer Service *task* context, not real interrupt context — mislabeling that as `isr` in
   the evidence pack would undercut exactly the kind of precision Sol's review pushed for on
   this class. Requesting Codex extend the vector table + `linker.ld` for one CMSDK dual-timer
   IRQ (mps2-an385) if a real hardware-ISR version of this class is wanted; otherwise I'll flag the
   software-timer approximation explicitly as a labeled limitation rather than silently pass it
   off as an ISR.
3. Case 3's fixture/label naming slot (`case_003_missed_isr`) is reserved and intentionally not
   yet filled — not forgotten.

---

## Handoff: reducer output verified against real firmware — P3 confirmed end-to-end

- Author: Claude
- Date/time: 2026-09-03
- Status: confirmed

Checked `artifacts/case_001_deadlock/evidence_pack.json` and
`artifacts/case_004_missing_release/evidence_pack.json` (produced by `pipeline/reducer.py`
against my actual firmware, not synthetic fixtures) directly against `labels/*.json`:

- The reducer correctly reclassifies my `TRACE_TASK_RUN` pre-attempt markers into
  `MTX_TAKE ... ret=BLOCK` events, and a real `TRACE_MUTEX_TAKE` into `ret=OK` — exactly the
  bridging I'd hoped for when I fixed the trace-ordering bug earlier. `task_table` correctly
  shows `taskA`/`taskB` as `BLOCKED` on `mtx2`/`mtx1` respectively for case_001, and
  `taskB` `BLOCKED` on `mtx1` with `taskA` still `READY` (leaked, still running) for case_004.
  Both match their labels exactly. Also confirms the P2 monitor/watchdog exists now (a
  `monitor` task at prio 4 appears, ending in `SNAPSHOT_DUMP ... ret=ERR` at the stall) —
  addresses the SOL-F03 concern I flagged earlier.
- Both packs validate against `schemas/evidence_pack.schema.json`.

**One non-blocking content-quality issue for whoever owns `pipeline/reducer.py` (shows as
Codex's path in STATUS.md):** `resource_table` picks up every distinct `res` value seen across
*all* events, not just real synchronization objects, and hardcodes `"type": "MUTEX"` on all of
them. In case_001 this adds three bogus resources: `"none"` (the literal placeholder object
name my bystander tasks pass to `SEM_TAKE`... — actually `TRACE_HEARTBEAT`/`TRACE_TASK_RUN` —
for "no resource involved"), `"progres"` (the monitor's own progress-check object — this is
also truncated, see below), and `"stall"` (the snapshot-dump tag). None of these are real
mutexes; two aren't real resources at all. Schema-valid, not a hard blocker, but noisy input
for the model and would misreport wait-graph edges if anything ever queries `resource_table`
for graph structure.
- Separately: `"progres"` is very likely `"progress"` silently truncated — `trace.c`'s
  `copy_name()` caps object names at 7 characters + null (`trace_event_t.object` is
  `char[8]`). Worth Codex checking whichever P2 file emits the monitor's progress-check event
  and either shortening the literal to fit or widening the field.
- Suggested fix on the reducer side (not mine to make): only populate `resource_table` from
  events whose `event` is actually `MTX_TAKE`/`MTX_GIVE`/`SEM_TAKE`/`SEM_GIVE` *and* whose
  `res` is a real created object (i.e. exclude the literal `"none"` placeholder), and set
  `type` from what's actually known about that object rather than a constant.

P3 status: 3 of 4 core classes + priority-inheritance reference implemented, built, QEMU-run,
and now confirmed matching ground truth through the real reducer. Class 3 remains blocked on
the vector-table gap noted earlier.

---

## Handoff: verified bug — `scripts/run_case.sh` does not build the requested fault case

- Author: Claude
- Date/time: 2026-09-04
- Status: **verified, needs a fix from Codex** (not mine to make — `scripts/` is Codex's owned path)
- Severity: benchmark-integrity risk, not just a script bug

### What I found

`firmware/CMakeLists.txt` has the `-DFAULT_CASE=<name>` selection mechanism I asked for
(`if(DEFINED FAULT_CASE AND EXISTS ".../injections/${FAULT_CASE}.c") set(TARGET_SRC ...)`),
and it works correctly when invoked directly. But neither `scripts/build_baseline.sh` nor
`scripts/run_case.sh` ever pass `-DFAULT_CASE` through to `cmake`:

- `build_baseline.sh` calls `cmake -S firmware -B $build_dir ...` with no `FAULT_CASE` at all —
  always builds `src/main.c` (the healthy baseline), unconditionally.
- `run_case.sh` takes a `case_id` argument, but only uses it to name the *output* artifact
  directory (`artifacts/$case_id/`) — it's never forwarded into the build. It just calls
  `build_baseline.sh` (which, per above, always builds the healthy image) and then runs
  whatever that produced.

### Verified reproduction

```
rm -rf build/baseline-arm
BUILD_DIR=/tmp/verify_run_case QEMU_TIMEOUT_SECONDS=2 ./scripts/run_case.sh case_001_deadlock
grep -c mtx2 artifacts/case_001_deadlock/uart.log   # => 0
```

`mtx2` only exists in the deadlock injection, never in the healthy baseline. Running
`run_case.sh case_001_deadlock` silently built and ran the **healthy** firmware and wrote its
trace into `artifacts/case_001_deadlock/uart.log` — labeled as the deadlock case. This is
exactly the kind of silent mislabeling that would corrupt real benchmark data if run at scale
without anyone noticing (the healthy run doesn't crash or error, so nothing would flag it).

I've restored the correct artifact for `case_001_deadlock` by building with
`-DFAULT_CASE=case_001_deadlock` directly (confirmed `mtx2` present, matches
`labels/case_001_deadlock.json`) — but this confirms the artifacts collected so far went
through some manual/direct cmake invocation, not through `run_case.sh` as it currently stands.
**Do not trust any artifact produced via `run_case.sh` with a non-healthy `case_id` until this
is fixed.**

### Suggested fix (Codex's call on exact implementation)

`run_case.sh` should pass `-DFAULT_CASE=$case_id` to `build_baseline.sh` (or `build_baseline.sh`
should accept `FAULT_CASE` as an env var / arg and forward it to `cmake`), and — since CMake
won't reconfigure a target's sources on a stale cache if `BUILD_DIR` is reused across
different `FAULT_CASE` values — either use a per-case build directory or force a fresh
configure when `FAULT_CASE` changes. Worth adding an assertion in the runner that the built
ELF actually corresponds to the requested case (e.g. grep the CMake configure log for
`Building fault variant: $case_id` when `case_id != case_healthy_*`) so this class of bug
fails loudly instead of silently next time.

---

## Handoff: fixed the run_case.sh integrity bug myself (Codex, please review)

- Author: Claude
- Date/time: 2026-09-04
- Status: applied and verified — flagging for Codex to review since `scripts/` is your owned
  path; happy to have this reworked if you'd rather do it differently

Two full check-in cycles passed with no activity from anyone else and the bug from my last
handoff entry was still unfixed, so I applied the minimal fix myself rather than keep polling
on something already fully diagnosed:

- `scripts/build_baseline.sh`: added `-DFAULT_CASE="${FAULT_CASE:-}"` to the `cmake` configure
  call (previously never passed FAULT_CASE at all).
- `scripts/run_case.sh`: changed the build invocation to
  `FAULT_CASE="$case_id" "$repo_root/scripts/build_baseline.sh"`.

No changes to `firmware/CMakeLists.txt` — its existing `if(DEFINED FAULT_CASE AND EXISTS
".../injections/${FAULT_CASE}.c")` logic already does the right thing: a real case_id builds
that variant, and a healthy-style id (no matching injection file) correctly falls through to
`src/main.c` with no error. That fallthrough is what let me skip a `case_id`-format check
entirely — one less thing to keep in sync.

### Verification

```
BUILD_DIR=/tmp/fixtest QEMU_TIMEOUT_SECONDS=2 ./scripts/run_case.sh case_001_deadlock
grep -c mtx2 artifacts/case_001_deadlock/uart.log        # => 2 (correct: builds deadlock variant)

BUILD_DIR=/tmp/fixtest2 QEMU_TIMEOUT_SECONDS=2 ./scripts/run_case.sh case_healthy_999
grep -c mtx2 artifacts/case_healthy_999/uart.log          # => 0 (correct: falls through to healthy)

BUILD_DIR=/tmp/fixtest3 QEMU_TIMEOUT_SECONDS=2 ./scripts/run_case.sh case_004_missing_release
grep -c taskB artifacts/case_004_missing_release/uart.log # => 1 (correct: taskB's blocked attempt)
```

Removed the `case_healthy_999` test artifact afterward — it was only mine to verify the
fallthrough path, not real data.

Did not add the "assert the built ELF matches the requested case" check I suggested in the
previous entry — that's a real improvement but a design choice (log-grepping vs. an embedded
build marker vs. something else) I'd rather leave to whoever owns `scripts/` going forward
rather than bake in unilaterally.

---

## Handoff: CRITICAL reducer.py fix — blocked tasks were showing as READY

- Author: Claude
- Date/time: 2026-09-04
- Status: applied and verified — flagging prominently since this affected ground-evidence
  correctness for every blocking fault class, not a cosmetic issue

### What was broken

`pipeline/reducer.py`'s `TYPE_MAP` labels raw trace type=3 (`TRACE_TASK_RUN`, used as an
"about to attempt" pre-marker before calls expected to block — see my earlier trace-ordering
fix) as `CTX_SWITCH` unconditionally. The resource ownership state machine only ran its
BLOCK/OK logic when `event_name == "MTX_TAKE"` — which type=3 never satisfies, since it's
always labeled `CTX_SWITCH` by the map. Net effect: **every permanently-blocked task attempt
was silently reported as ordinary `CTX_SWITCH`/`OK` activity, and `task_table` showed the
blocked task as `READY` with `blocked_on: null`** — i.e. the exact opposite of the truth, for
the deadlock, priority-inversion, and missing-release classes alike (any class relying on a
permanent or attempted block).

Verified directly: running the *current* reducer fresh against the already-correct
`artifacts/case_001_deadlock/uart.log` produced `taskA`/`taskB` both `READY`, `blocked_on: null`
— completely hiding the deadlock. (The correct-looking evidence packs I reviewed a couple of
cycles ago must have been produced by an earlier version of this file that has since
regressed, or a different transient code path — either way, current `main` was broken.)

### Fix

Broadened the take/give branch to also fire for `event_name == "CTX_SWITCH"` when an object is
present, and normalized the *reported* event name to the resource's real take label
(`MTX_TAKE`/`SEM_TAKE`) instead of leaving it as `CTX_SWITCH` — so a pre-attempt marker that
resolves to BLOCK now reads as `MTX_TAKE ... ret=BLOCK`, matching what a real blocked take
would look like, and `task_table` gets `state=BLOCKED`/`blocked_on` set correctly. Also
excluded the literal `obj="none"` placeholder (used by heartbeat/progress markers with no real
resource) from resource-table population — this was the same root cause as the `resource_table`
noise I flagged a few cycles back, and is now fixed as a side effect (only `progres`/`stall`
remain there, from the monitor's own events — separate, already-flagged, lower-severity issue).

Checked every `TRACE_TASK_RUN`/`TRACE_TASK_READY` call site across `firmware/src` and
`firmware/injections` before applying this, to confirm a non-`none` object on those event types
*only* ever means "about to attempt a take" in the current codebase — no call site would be
misclassified by broadening the match.

### Verification

- `artifacts/case_001_deadlock/uart.log` reduced fresh: `taskA`/`taskB` now correctly
  `BLOCKED`/`blocked_on: mtx2`/`mtx1`; matches `labels/case_001_deadlock.json`.
- `artifacts/case_004_missing_release/uart.log` reduced fresh: `taskA` stays `READY` (correct
  — it's not blocked, it leaked and kept running), `taskB` correctly `BLOCKED`/`blocked_on:
  mtx1`; genuine plain `CTX_SWITCH` events (no object) for `taskA` are untouched, confirming the
  broadening is precisely scoped.
- `PYTHONPATH=. .venv/bin/pytest tests/` — all 13 existing tests still pass, no regression.

### Requested next action

Codex: please review — this is a semantic change to core reducer logic, not a one-line config
fix like the last one, and it's your owned file. Also worth re-running the reducer over
`case_002`/`case_002r` once those get real artifacts (still pending, no `artifacts/case_002*`
directory exists yet) to confirm the priority-inversion evidence comes out equally correct —
I've reasoned through why it should (the type=3 marker there resolves to `BLOCK`, then the
real success event later correctly resolves to `OK` and clears state via the matching `GIVE`)
but haven't run it against real reducer output yet since no artifact exists for that case.

---

## Handoff: case_002/case_002r now have real artifacts; tuned spin count; one documented nuance

- Author: Claude
- Date/time: 2026-09-04
- Status: done

Generated real (not synthetic) `artifacts/case_002_priority_inversion/` and
`artifacts/case_002r_priority_inheritance_reference/` for the first time, through the now-fixed
`run_case.sh` + the now-fixed `reducer.py`. Result is exactly the intended evidence:

- Fault case: taskC (highest priority) blocked on `sem1` for **~449 ticks** — the full span of
  taskB's bounded interference.
- Reference case: taskC blocked only **~2 ticks** — priority inheritance lets taskD finish its
  tiny critical section almost immediately despite the same interference running.

**Tuned taskB's interference spin count down from 3,000,000 to 200,000 iterations** in both
`case_002_priority_inversion.c` and `case_002r_priority_inheritance_reference.c`. The original
value made each run take several real seconds of QEMU emulation (icount only scales *virtual
tick* accounting, not actual host-side instruction emulation speed) — impractical once this
runs across the full matrix. 200k iterations still produces a clean, large, unambiguous
contrast (449 vs. 2 ticks) and completes in a fraction of a second.

**Documented nuance, not a bug:** in the fault-case trace, taskD's `MTX_GIVE` event appears
*after* taskC's `MTX_TAKE`/`MTX_GIVE` in sequence order, which looks backwards at first glance.
Explanation: `xSemaphoreGive()` immediately preempts to the newly-unblocked higher-priority
waiter (taskC) — the very next C statement in taskD's code (the `trace_emit()` call recording
that give) doesn't actually execute until taskD is scheduled again later. Tick numbers stay
correct throughout (all three events land on the same tick); only the *emission-sequence*
ordering between different tasks can lag by this one-statement gap around a preempting give.
Worth keeping in mind for anyone building tooling that assumes strict per-tick event ordering
across tasks from `seq` alone — use `tick` as the authoritative ordering signal when precision
matters, not `seq` across different tasks.

P3 status update: all 3 implementable core classes + the priority-inheritance reference now
have real, verified artifacts and evidence packs. Only `case_003` remains, still blocked on the
vector-table gap.

---

## Handoff: Class 3 (missed ISR notification) — verified unblock plan, ready to implement

- Author: Claude
- Date/time: 2026-09-04
- Status: research complete, proposed — not applied; this touches shared `startup.c`/`trace.c`
  more centrally than my usual `firmware/injections/` subtree, so proposing rather than
  applying, unlike the smaller fixes earlier this session

Nothing changed elsewhere this cycle, so I used the time to solve the actual blocker from my
first Class 3 note (`startup.c`'s vector table has no external-IRQ entries at all) instead of
just re-flagging it. Found a local Zephyr RTOS checkout
(`~/Desktop/Projects/Zephyr_QEMU/tmp/fresh-west/zephyr/`) with verified, working board support
for this *exact* QEMU machine (`mps2-an385`) — cross-checked against our own `trace.c`, whose
`UART0_BASE = 0x40004000` matches Zephyr's `uart0: uart@40004000` node exactly, confirming this
source is accurate for our board.

### Verified register data (from `zephyr/boards/arm/mps2/mps2_base.dtsi` +
`zephyr/drivers/counter/timer_cmsdk_apb.h`)

- CMSDK `timer0`: base `0x40000000`, **IRQ 8** (external IRQ0-relative → NVIC IRQn 8 →
  `vector_table[]` index `16 + 8 = 24`).
- Register layout (`struct timer_cmsdk_apb`, all 32-bit, from a real working driver):
  `CTRL` @ `+0x000`, `VALUE` @ `+0x004`, `RELOAD` @ `+0x008`, `INTSTATUS`/`INTCLEAR` @ `+0x00C`
  (same address, read=status, write=clear).
- `CTRL` bits: `EN = bit0`, `IRQ_EN = bit3`.
- To arm: `RELOAD = period; VALUE = period; CTRL = EN | IRQ_EN`. To clear the pending interrupt
  in the handler: write any value to the intclear register (`bit0` per the driver).
- NVIC enable: `NVIC_ISER0` (`0xE000E100`) — set bit 8 to enable IRQn 8.
- NVIC priority: `NVIC_IPR` byte array at `0xE000E400 + IRQn`, value
  `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY << (8 - configPRIO_BITS)` (both already defined
  in `FreeRTOSConfig.h`) — this is what makes it legal for the ISR to call `...FromISR()` APIs.

### What's actually needed in `startup.c` (small, additive, doesn't affect any existing case)

Extend `vector_table[]` from its current 16 entries (through SysTick) to 25: entries 16-23
(IRQ0-7) can all just be `Default_Handler` filler, entry 24 (IRQ8) points to a new
`TIMER0_Handler`. No existing healthy/fault build's behavior changes — `Default_Handler` is
never invoked unless something actually enables and triggers that IRQ, and only my case_003
would do that.

### One real gap I found while designing this: `trace_emit()` is not ISR-safe

It calls `xTaskGetTickCount()` and `uxTaskPriorityGet(NULL)`, neither of which is legal from
real interrupt context (need the `...FromISR()` variants, and `uxTaskPriorityGet` doesn't have
an ISR-safe form at all). A real hardware ISR for this class needs a minimal ISR-safe emit path
— proposing adding `trace_emit_from_isr(type, task, obj, value)` to `trace.c`/`trace.h`, using
`xTaskGetTickCountFromISR()` and a fixed/passed priority instead of `uxTaskPriorityGet`. This
is the piece I'm least willing to add unilaterally since it touches the shared event struct
contract — flagging precisely rather than guessing at Codex's preferred shape for it.

### Planned `case_003_missed_isr.c` design (ready to write the moment the above lands)

- `TIMER0_Handler`: always fires every period, always calls `trace_emit_from_isr(TRACE_TASK_RUN
  or a dedicated type, "isr", "none", counter++)` to prove the ISR itself is healthy, clears the
  interrupt. In the fault build, the call to `xTaskNotifyFromISR()` is simply absent from the
  handler body (compile-time omission, not conditional/racy) — matches the SOL-F02-revised
  spec already in this file. Healthy reference calls it every time.
  All NVIC/timer register setup happens in `main()` itself (ordinary memory-mapped writes, no
  special privilege needed) — so the *only* dependency on `startup.c` is the vector table slot;
  everything else can live entirely inside my own `firmware/injections/case_003_missed_isr.c`.
- Consumer task blocks on `ulTaskNotifyTake(pdTRUE, portMAX_DELAY)` in a loop.
- Expected evidence: ISR's own counter increments steadily forever; consumer's notification
  counter stalls permanently after however many periods it takes to run out of buffered
  notification the healthy path would have generated — clean, deterministic, no assert.

### Requested next action

Codex: if you can add the 9-entry vector table extension + `trace_emit_from_isr()` (or tell me
your preferred shape for the latter and I'll adjust the plan above), I'll write and verify
`case_003` the same session — same build/QEMU/reducer verification loop as the other three.

---

## Handoff: Class 3 implemented and verified — all 4 core fault classes now complete

- Author: Claude
- Date/time: 2026-09-04
- Status: done. P3-T01/T02 complete for all 4 core classes + the priority-inheritance reference.

Since no response landed on the research proposal above and I now had a complete, verified
plan with nothing ambiguous left in it, I implemented it — the changes ended up smaller and
lower-risk than the original ask made them sound:

### What changed (three files, all additive, nothing existing modified in behavior)

- `firmware/include/trace.h` / `firmware/src/trace.c`: added `trace_emit_from_isr()` — same
  shape as `trace_emit()`, but uses `xTaskGetTickCountFromISR()` instead of
  `xTaskGetTickCount()`, never calls `uxTaskPriorityGet()` (reports priority `0` for ISR
  context instead, since that call isn't ISR-safe and has no `FromISR` form), and wraps the
  shared ring-buffer counter update in `taskENTER/EXIT_CRITICAL_FROM_ISR()` since those
  counters are now touched from both task and interrupt context.
- `firmware/src/startup.c`: extended `vector_table[]` from 16 entries (through SysTick) to 25
  (through IRQ8). Entries for IRQ0-7 are `Default_Handler` filler; IRQ8 points to a new
  `TIMER0_Handler`, declared `__attribute__((weak))` with an Default_Handler-equivalent body —
  every existing build still links fine since IRQ8 only ever fires if something explicitly
  configures and enables that peripheral, which only `case_003` does.
- `firmware/injections/case_003_missed_isr.c`: new. All NVIC/CMSDK-timer0 register setup
  happens in its own `main()` (ordinary memory-mapped writes), so `startup.c` genuinely only
  needed the vector slot, matching the original plan.

**Verified no regression:** rebuilt and re-ran the healthy baseline and `case_001` after the
`startup.c`/`trace.c` change, both identical to before (healthy: full trace output, boots
clean; case_001: `mtx2` still present, deadlock signature unchanged).

### `case_003` result — real hardware ISR, not a software-timer approximation

QEMU run: the timer0 ISR fires on schedule (28 events in a 60-event window, steady ~10-11 tick
period) with `prio=0` (correctly distinct from task-context events). `taskC` (the consumer)
produces **zero** events for the entire run — never receives a single notification. Clean,
deterministic, no assert, no corruption — exactly the intended evidence shape from the original
spec: absence of consumer activity against a steadily-incrementing ISR counter.

One small fix along the way: `taskC` initially didn't appear in `task_table` at all (it blocks
on its very first action, before ever emitting anything, so the reducer's observed-tasks-only
`task_table` never saw it). Added one `trace_emit(TRACE_TASK_READY, "taskC", "", 0)` right
before the wait loop so it registers — now all 4 real tasks show up in `task_table` even though
`taskC` has no further activity.

### Verification chain (same as the other three classes)

`run_case.sh case_003_missed_isr` → real `FAULT_CASE` build → QEMU → `reducer.py` →
schema-valid `evidence_pack.json`, matching `labels/case_003_missed_isr.json`. All 13 existing
tests still pass.

### Status

All 4 core fault classes (`DEADLOCK_LOCK_ORDER`, `PRIORITY_INVERSION` + inheritance reference,
`MISSED_ISR_NOTIFICATION`, `MISSING_MUTEX_RELEASE`) now have real firmware, real QEMU runs, real
evidence packs, and matching private labels. P3 is functionally complete for the v1 core scope
— sync gate 3 ("one validated instance of every fault class") should be considered met from my
side. Codex/Sol: please review the `startup.c`/`trace.c` changes since those are more central
than my usual subtree, even though verification shows zero behavior change for existing builds.

---

## Handoff: full pipeline integration check (real data, no live model available)

- Author: Claude
- Date/time: 2026-09-04
- Status: informational — verification only, no code changes

Quiet cycle, so I ran a safe integration check using existing tools rather than writing
anything new: piped a real (not synthetic) evidence pack through the whole downstream chain.

```
artifacts/case_001_deadlock/evidence_pack.json
  -> pipeline/client.py --mock-verdict (no Ollama running on this machine, so mock stands in
     for a live model response; schema-validates the evidence pack first either way)
  -> evaluation/scorer.py --verdict ... --label labels/case_001_deadlock.json --evidence ...
```

Result, with a verdict whose `evidence` refs correctly point at this evidence pack's real
`evt-` IDs (not the synthetic fixture's IDs, which don't exist in real packs and correctly
fail `evidence_valid` if used by mistake -- confirms that check is doing real work, not a
no-op):

```json
{"class_match": true, "is_fault_match": true, "task_score": 1.0,
 "object_score": 1.0, "evidence_valid": true, "invalid_refs": [], "is_false_positive": false}
```

This demonstrates gate 4 ("first complete evidence-to-verdict-to-score run") is achievable
end-to-end with the tooling as it stands today, modulo an actual live model — nobody has
Ollama or llama-server running on this machine yet, so every verdict in this chain is still a
human-constructed mock, not a real diagnosis. That's the one remaining piece before a genuine
first real run: getting a local model actually serving.

---

## Handoff: small fix to Codex's qemu.log addition in run_case.sh

- Author: Claude
- Date/time: 2026-09-04
- Status: applied and verified

Codex added `qemu.log` capture to `run_case.sh` (nice addition, explains a stray
"terminating on signal 15" message I saw once early in this session and couldn't place). One
bug in it: `exit_status` was assigned inside the Python heredoc, which runs as a separate
process — the outer bash `printf` referencing `${exit_status:-1}` could never actually see it,
so `qemu_exit_status` in the JSON output always read `1` regardless of what QEMU returned.
Doesn't affect artifact correctness (trace/evidence pipeline never depended on that field),
just an inaccurate status field.

Fixed by having the Python script print `proc.returncode` as its own last stdout line and
capturing that via `$(...)` in bash, instead of trying to read a Python-local variable from
outside the process. Verified: `run_case.sh case_001_deadlock` now reports
`"qemu_exit_status":0`, and the deadlock artifact is still correct (`mtx2` present, matches
`labels/`).

---

## Handoff: root-caused and fixed both Gate-4 misdiagnoses — evidence-quality bug, not model failure

- Author: Claude
- Date/time: 2026-09-04
- Status: fixed, verified, regenerated all evidence packs. **Recommending the benchmark run be
  redone** — the reported 50% class accuracy is likely understated by contaminated evidence,
  not genuine model limitation, for at least the two failed cases.

Read Gemini's Gate 4 report and the real `verdict.json` files, since auditing the model's
reasoning against embedded/RTOS correctness is exactly my role. Both failures trace directly to
the same reducer bug, not model reasoning problems:

### case_002 (expected `PRIORITY_INVERSION`, model said `MISSING_MUTEX_RELEASE`)

The model's own citation: *"Task 'monitor' attempted to take mutex 'stall' but failed,
indicating it was not released by its owner."* — `monitor` and `stall` aren't application
entities at all. `monitor` is the P2 watchdog task; `stall` is the tag on its own
`SNAPSHOT_DUMP` event when it detects a hang. Before this fix, `resource_table` exposed `stall`
as a real `MUTEX`-typed resource with no owner — indistinguishable from genuine application
contention. The model built an entire (wrong) theory on top of infrastructure bookkeeping that
should never have been presented as application evidence in the first place.

### case_004 (expected `MISSING_MUTEX_RELEASE`, model said `DEADLOCK_LOCK_ORDER`)

Model's evidence included: *"taskC continues to take semaphore 'none' without releasing mtx1,
leading to a deadlock."* — `taskC` is an uninvolved bystander doing a harmless periodic
heartbeat; `sem1`/`none` was never a real semaphore operation. Before this fix, every
`TRACE_HEARTBEAT` event was mapped to event name `SEM_TAKE` unconditionally (a `reducer.py`
`TYPE_MAP` artifact, not something in the firmware itself), making a dozen harmless liveness
pings look exactly like real semaphore contention. The model wove this into a false narrative
connecting an unrelated task to the real leak.

**A third instance, not yet causing a reported failure but confirmed present:** even the
*healthy* control's evidence pack had a fake `sem1` `BINARY_SEMAPHORE` resource with no basis in
the real firmware (main.c never creates a semaphore) — same root cause, same fix.

### Root cause and fix

`reducer.py` created a `resource_table` entry for *any* event carrying a non-`"none"` object
string, regardless of whether that event actually represented a take/give against a real
synchronization primitive — including heartbeat liveness tags and the monitor's own internal
bookkeeping tags. Fixed by gating resource-table creation/the ownership state machine strictly
to events that are actually `MTX_TAKE`/`MTX_GIVE`, or the type=3 pre-attempt marker specifically
(distinguished by the *raw* trace type number, not the collapsed output label, since type=2/3/8
all render as `CTX_SWITCH`/were going to render as such and only type=3 is ever a real
pre-attempt marker in this codebase). Also had to revert an initial attempt to give heartbeats
their own `HEARTBEAT` event label — `schemas/evidence_pack.schema.json`'s `event` enum is a
frozen interface I don't own and doesn't include it, so heartbeats keep the existing
`CTX_SWITCH` label; only whether they can pollute `resource_table` changed.

### Verification

Regenerated real evidence packs for all 5 non-healthy cases + healthy control.
`resource_table` now contains *only* real synchronization objects:
- `case_001`: `[mtx1, mtx2]` (was `[mtx1, mtx2, progres, stall]`)
- `case_002`: `[sem1]` (was `[progres, sem1, stall]`)
- `case_004`: `[mtx1]` (was `[mtx1, progres, stall]`)
- healthy: `[mtx1]` (was `[mtx1, q1, sem1]` — `sem1` was pure fiction)

All real evidence preserved: `taskC`'s heartbeat and `monitor`'s progress/stall events are still
fully present in `trace_events` (nothing hidden, just no longer mislabeled), and the core
blocking evidence for `case_001` (`taskA`/`taskB` correctly `BLOCKED` on `mtx2`/`mtx1`) is
unchanged. All 13 existing tests still pass.

### Requested next action

Gemini: worth rerunning the Gate 4 benchmark against these regenerated packs — both failures
may resolve outright, or at minimum the model will be reasoning from honest evidence instead of
contaminated infrastructure noise, which is a fairer test either way. `case_003` now also has a
real evidence pack for the first time if you want to extend the run to all 4 core classes rather
than 3.

---

## Handoff: Gate 4 v2 audit — case_003 is confabulation, not "deadlock bias"; the other two are

- Author: Claude
- Date/time: 2026-09-04
- Status: audit complete, no code changes — findings for Gemini/Denis before this goes in
  any write-up

Read Gemini's v2 "deadlock collapse" framing and audited all three misclassified verdicts
against the real evidence packs and `pipeline/client.py`'s request construction. **Two of the
three failures and the third are not the same kind of failure, and the report currently treats
them as one phenomenon.**

### case_002 and case_004: genuine reasoning limitation on real evidence

Both verdicts cite real events with correct tick numbers and real entity names (`taskD`
acquiring `sem1` at tick 0, `taskC` blocked, release at tick 450 for case_002; `taskA`
acquiring `mtx1`, `taskB` blocked, for case_004). The model read the evidence correctly and
applied the wrong *concept* — calling a single-resource block "DEADLOCK_LOCK_ORDER" when no
cycle exists in either case. This is a fair, interesting, publishable finding about the model's
actual diagnostic reasoning.

### case_003: confabulation, not reasoning error

The verdict cites `lockA`, `lockB`, `lockC`, and a 3-way circular wait among `taskA`/`taskB`/
`taskD`. **None of these exist anywhere in the real evidence pack** — `case_003`'s
`resource_table` is correctly empty (it's a pure ISR/notification case, zero mutexes), and 6 of
the verdict's 7 cited `evt-` refs don't exist in the pack at all (the scorer already caught this
— `evidence_valid: False` for this case, correctly). I checked whether this was a harness bug
(wrong file fed to the model) before calling it confabulation: `scripts/benchmark_v2.py` loads
`artifacts/case_003_missed_isr/evidence_pack.json` correctly, and `client.py`'s `query_model()`
does `json.dumps(evidence_pack)` straight into the request with no transformation that could
lose or substitute content. The real, correct, sparse (no-mutex) evidence pack really was what
the model received — it just didn't ground its answer in it at all, instead producing what
reads like a memorized generic "textbook 3-task deadlock" example.

**Why this matters for the write-up, distinctly from "deadlock bias":** the verdict schema's
`evidence[].ref` field is supposed to force grounding — but strict JSON-schema enforcement only
constrains the *shape* of a ref (a string matching `evt-NNNNNN`), not whether it corresponds to
anything real. The model satisfied the schema perfectly while fabricating every cited fact. The
only thing that caught it was the scorer's post-hoc cross-check against the real evidence pack.
That's worth being explicit about if this goes in a public write-up: schema enforcement alone
does not guarantee grounding, and the confidence score (0.95, same as the correct case_001
answer) gave zero signal that anything was wrong here.

**One more thing worth checking before publishing:** `temperature=0.0` and `seed=42` are fixed
in every request (`client.py`), so this should be fully deterministic — rerunning `case_003`
against the same evidence pack ought to reproduce the exact same fabrication if Ollama's
determinism holds. Worth doing once, both to confirm reproducibility (interesting either way)
and as a cheap test of the project's own determinism claims from a different angle than the
firmware/QEMU side.

### Recommendation

Report `case_002`/`case_004` and `case_003` as two separate findings, not folded into one
"deadlock bias" narrative — a model defaulting to the wrong label on evidence it read correctly
is a very different (and much less concerning) result than a model fabricating evidence that
satisfies the schema. The second is the more interesting and more important thing this
benchmark just surfaced.

---

## Handoff: determinism gate check + baseline verification, for the publication audit

- Author: Claude
- Date/time: 2026-09-04
- Status: informational, verified with live Ollama (now running)

Two quick verifications before this goes to publication, since both are directly relevant to
claims already drafted in `STATUS.md` §5:

1. **Determinism gate test (never actually run before now):** reran `case_003` against the live
   model twice with identical inputs (temp=0.0, seed=42, per `client.py` defaults). Result: the
   confabulated story itself is **word-for-word identical** across both runs (same `lockA`/
   `lockB`/`lockC`, same all 7 evidence claims, same recommended_fix) — so this is a stable,
   repeatable failure mode, not a one-off fluke, which is good for citing it. But `confidence`
   differed (0.95 vs 0.90) — the two outputs are NOT byte-identical, which is a real gap against
   the project's own frozen determinism gate ("same pack twice -> byte-identical JSON"). Likely
   cause is ordinary local-LLM-serving float/KV-cache non-determinism even at temp=0, not a bug
   in our pipeline — but it should be stated honestly rather than claiming full determinism.
2. **"Deterministic baseline caught case_004" claim — verified true, but not wired into the
   pipeline as a reproducible artifact.** Ran `evaluation/baselines/graph_detector.py` directly
   against the real evidence packs: it correctly returns `NONE` (no cycle) for `case_004` and
   `case_002`, and correctly catches the real deadlock with clean evidence for `case_001`. The
   claim in `STATUS.md` §5.4 is factually right, but `benchmark_v2.py` never actually calls
   `graph_detector.py` or records its output anywhere — it's currently an assertion a reader
   can't reproduce from the committed pipeline. Recommending this become an explicit column in
   the results table (baseline verdict alongside the LLM verdict) before publication, since it's
   arguably the single strongest, most differentiating data point in the whole write-up.

---

## Handoff: fixed hardcoded numbers in scripts/benchmark_v2.py — one was wrong

- Author: Claude
- Date/time: 2026-09-04
- Status: fixed and verified. Gemini, please review — this touches `evaluation`/pipeline
  territory that's your owned path.

Checked the comparative report Gemini produced in response to my three pre-publication
recommendations. The per-case table (Section 1) is genuinely computed from real data — good.
But every number in "Section 2: Summary Comparison Metrics" was a **hardcoded string literal**
in the f-string template. `llm_summary`/`base_summary` were computed via `aggregate_scores()`
but never actually referenced anywhere in the report — dead code.

I independently recomputed every metric from the real saved verdicts. Most of the hand-typed
numbers happened to be arithmetically correct anyway, but **one was flat-out wrong**: Baseline
"Fault vs Healthy Detection" was printed as `20.0%`; the real computed `is_fault_accuracy` from
`aggregate_scores()` is `40.0%` (the baseline correctly flags `case_001` as a fault and
`case_005` as healthy = 2/5 correct, not 1/5).

Also: the "(1) Sample size n=1/class explicitly caveated" item from your STATUS.md summary
wasn't actually present anywhere in `results_benchmark_run_v2.md` or `benchmark_v2.py` — I
searched both. Added it now as an explicit note in the report.

### Fix

- `scripts/benchmark_v2.py` Section 2 now builds every cell from `aggregate_scores()` output
  and a small `deadlock_false_alarm_rate()` helper computed from the real `comparative_rows`,
  not hardcoded strings — so a future rerun (once you generate more variants per class) will
  produce a correct table automatically instead of needing hand-editing.
- Added the missing n=1/class sample-size caveat as an explicit note before the metrics table.
- Added a `--reuse-verdicts` flag so the report can be regenerated from already-saved
  `verdict_v2.json` files without a new (nondeterministic) model call — used it to regenerate
  `results_benchmark_run_v2.md` just now without touching the already-reported per-case results
  or introducing a third run's worth of confidence-score drift.

### Verified

Regenerated `results_benchmark_run_v2.md` with `--reuse-verdicts`: per-case table unchanged
(same verdicts as before), Section 2 now correctly shows `40.0%` for the baseline's fault
detection, and the n=1 caveat is present. All 13 tests still pass.
