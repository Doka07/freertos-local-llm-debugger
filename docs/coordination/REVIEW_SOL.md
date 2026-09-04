# Sol Senior Architecture Review

**Reviewer:** Sol  
**Date:** 2026-09-03  
**Baseline reviewed:** `PLAN_MERGED.md` and current coordination handoffs  
**Verdict:** Approve the architecture conditionally; resolve the blocking items below before
implementation branches diverge or benchmark data is collected.

This review preserves the approved plan as the baseline. Proposed changes are additive
clarifications and gates; Denis remains the final authority.

## Executive findings

The core architecture is sound: a deterministic firmware experiment produces a blinded,
bounded evidence pack; a local model returns a structured verdict; an independent scorer
compares it with private labels. The four-class scope is appropriate for the first integrated
run.

There are three blocking coordination/setup issues and five important benchmark-quality
changes. None requires restarting the plan.

## Blocking before parallel implementation

### SOL-B01 — Canonical task IDs and ownership

`PLAN_MERGED.md`, `STATUS.md`, and `handoffs_gemini.md` currently assign conflicting owners and
IDs to `reducer.py`, `client.py`, and the deterministic baseline. This will create overlapping
edits and makes handoff status ambiguous.

Adopt this canonical map:

| ID | Deliverable | Owner |
|---|---|---|
| P0-T02 | Evidence-pack and verdict schemas plus synthetic fixtures | Gemini; Codex approves interface |
| P1-T01..T03 | Toolchain/setup, healthy firmware, deterministic QEMU runner | Codex |
| P2-T01..T03 | Trace recorder, watchdog/snapshot, artifact collector | Codex; Claude reviews |
| P3-T01..T03 | Fault specifications, injection implementations, private labels | Claude |
| P4-T01 | Ollama client and schema enforcement | Gemini |
| P4-T02 | Prompt and inference configuration | Gemini |
| P4-T03 | Model determinism and resource metrics | Gemini |
| P5-T01 | Deterministic artifact reducer and leakage checks | Codex |
| P5-T02 | Resumable end-to-end runner | Codex |
| P6-T01 | Scorer and result tables | Gemini |
| P6-T02 | Deterministic wait-for-graph baseline | Gemini |

Only the canonical map should appear in future status/handoff updates.

### SOL-B02 — Environment bootstrap is a real gate

Read-only checks on 2026-09-03 found:

- `qemu-system-arm`: not installed or not on `PATH`.
- `arm-none-eabi-gcc`: not installed or not on `PATH`.
- Project root: no `.git` repository; only `.venv/` and `docs/` currently exist.

Before marking P1 in progress, add a setup task that installs or locates the tools, pins exact
versions, obtains a pinned FreeRTOS source revision, records licenses/hashes, initializes Git,
and proves that `mps2-an385` is supported by the installed QEMU build. QEMU record/replay must
be tested experimentally on this exact machine rather than assumed.

### SOL-B03 — Freeze prompt before scorer access to labels/results

Gemini owns both prompt/model behavior and label-based evaluation. That is workable only with
a temporal firewall:

1. Gemini commits the prompt, inference parameters, schemas, and synthetic tests first.
2. Record their hashes and mark them frozen.
3. Only then may Gemini access labels and benchmark verdicts to run scoring.
4. Any later prompt/schema/context-selection change invalidates prior benchmark results and
   requires a complete rerun under a new experiment version.

Codex, as reducer owner, must not use private labels or injection source while designing
evidence selection. Claude, as label/injection owner, must not tune the prompt or scorer.

## FreeRTOS fault-realism audit

### SOL-F01 — Make fault timing deterministic by construction

Do not rely on arbitrary tick delays to arrange lock ownership. Use explicit startup gates or
barriers so both deadlock tasks demonstrably hold their first mutex before either requests its
second. Use the same method to force low-holder/high-waiter/medium-runner ordering in the
priority-inversion case. Delays can remain workload parameters after the ordering is proven.

For the binary-semaphore inversion variant, initialize the semaphore to the available state
before the low-priority task takes it. Capture both base and effective task priority; otherwise
the priority-inheritance reference cannot be demonstrated.

### SOL-F02 — Use one safe, deterministic missed-notification mechanism in core v1

The current Claude handoff combines two materially different bugs: calling a non-ISR-safe API
from an ISR and losing/coalescing notifications. A non-ISR-safe call can assert or corrupt
state; it does not reliably model a silently missed notification.

For the core case, use a timer ISR that still fires and increments a neutral ISR counter but
deterministically omits the `xTaskNotifyFromISR()` call in the faulty branch. The consumer then
remains blocked while ISR progress continues. Keep invalid ISR API usage and notification
overwrite races as future, separately labelled classes.

### SOL-F03 — Watchdog cannot depend on the idle hook

A CPU-bound medium-priority task in the inversion case can prevent the idle task from running,
so an idle-hook watchdog may never execute. Use a small highest-priority monitor task awakened
periodically by the tick to inspect per-task progress counters, plus a host-side QEMU timeout as
a final collection guard. The monitor is infrastructure, not one of the four workload tasks,
and its runtime overhead must be measured.

## QEMU determinism audit

### SOL-D01 — Separate three determinism claims

Test and report these independently:

1. Build determinism: pinned sources/tools produce identified firmware artifacts.
2. Execution determinism: repeated fixed-input QEMU runs produce equivalent event sequences;
   byte-identical logs are stronger but should not be assumed before testing.
3. Inference determinism: identical evidence and parameters produce equivalent parsed verdicts.

If byte-identical inference fails, preregister repeated trials and report variance. Do not call
the entire benchmark deterministic merely because `-icount` is enabled.

`-icount shift=7` is a proposed parameter, not a validated constant. Compare at least one
timing-sensitive case with and without it before freezing the value.

## Evidence leakage and observability audit

### SOL-E01 — JSONL is the artifact contract, not necessarily the firmware hot path

Formatting JSON and synchronously writing UART inside scheduling/ISR paths can perturb the very
timing being measured. Record compact fixed-size events into a bounded RAM ring buffer with a
monotonic sequence number. Convert the collected buffer to canonical JSONL on the host. UART may
carry low-rate health/status output, but the in-memory event stream is authoritative.

Every emitted event and source excerpt in the evidence pack must have a stable neutral ID.
Replace free-form evidence claims in the verdict with `evidence_refs` to those IDs, optionally
plus a short explanation. This makes evidence grounding auditable rather than purely subjective.

### SOL-E02 — Enforce an explicit access and export matrix

Document machine-checkable allowlists:

| Consumer | Allowed | Forbidden |
|---|---|---|
| Reducer development | Raw neutral artifacts, schemas, synthetic fixtures | Labels, friendly variant map, injection source |
| Model invocation | Final evidence pack and verdict schema | Entire repository, paths, labels, build flags, comments |
| Scorer after prompt freeze | Verdicts, labels, experiment manifest | Injection source |
| Publication build | Approved results and sanitized examples | Private mappings unless explicitly released |

Leakage tests should inspect both keys and values, source excerpts, metadata, file names, prompt
logs, and error messages. Run a canary test containing forbidden markers and prove packaging
fails closed.

## Scope and scoring audit

### SOL-S01 — Preregister before real model output

Before querying the model on any real case, freeze and hash:

- exact case matrix and healthy-control count;
- prompt, model digest, inference parameters, schemas, reducer version, and token budget;
- primary and secondary metrics;
- handling of schema failures, retries, ties, partial credit, and missing evidence;
- number of repeated inference runs per case;
- rules for excluding failed firmware runs.

Four variants per class are enough for engineering demonstration coverage, but not for broad
statistical claims. Report exact counts and confidence intervals where meaningful, and avoid
generalizing beyond the constructed cases. Include enough healthy runs to make the false-positive
rate visible rather than relying on one healthy example.

### SOL-S02 — Keep classification and reasoning scores separate

Primary machine scores should include class exact match, culprit task/object set scores,
schema validity, and healthy false-positive rate. Evidence grounding should use stable
`evidence_refs`. Fix correctness and “right answer for the right reason” remain blinded human
adjudications with a written rubric; do not silently fold subjective judgments into one
accuracy number.

## Recommended approval

Approve SOL-B01 through SOL-S02 as amendments to the existing plan. After approval:

1. Codex updates the canonical task board and completes environment bootstrap.
2. Gemini freezes schemas/prompt/synthetic tests without labels.
3. Claude updates the missed-notification and deterministic-ordering fault specs.
4. Parallel implementation resumes at the first synchronization gate.
