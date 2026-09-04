# FreeRTOS Local-LLM Debugger — Merged Coordination Plan

**Status:** APPROVED — design frozen with Sol amendments; Luna implementation authorized  
**Date:** 2026-09-03  
**Project owner / final arbiter:** Denis Krutskih  
**Integration owner:** Codex  
**Embedded owner:** Claude  
**LLM/evaluation owner:** Gemini

This is the authoritative working plan synthesized from the three proposals and the approved
Sol architecture review. Luna agents implement this plan. Material changes require a recorded
decision and Denis approval before implementation continues in the affected area.

## 1. Goal and success criterion

Build a measured, reproducible benchmark—not an autonomous-debugging demo—in which FreeRTOS
firmware runs on a QEMU Cortex-M3 target, emits structured execution evidence, and a local
Qwen-family model produces a blind JSON diagnosis. Results are scored against private labels,
including healthy-case false positives and confidently wrong explanations.

The v1 claim must be limited to the tested target, firmware, fault classes, model versions,
and measured evidence. The model is a pure JSON-to-JSON function in v1; it has no shell, GDB,
or firmware-control access.

## 2. Approved design freeze

- Target: FreeRTOS on QEMU `mps2-an385` / Cortex-M3.
- Reproducibility is tested separately for the build, QEMU execution, and model inference.
  `-icount shift=7` is a candidate setting that must be validated on a timing-sensitive case;
  use QEMU record/replay if the installed build supports it. Any weaker fallback claim must be
  recorded before benchmark collection.
- Evidence flow: firmware artifacts → deterministic reducer → blinded evidence pack → local
  model → schema-validated verdict → private scorer.
- Public identifiers are neutral (`taskA`…`taskD`, `mtx1`, `mtx2`, `q1`, `sem1`). No fault
  names, injection macros, source-tree paths, or ground-truth labels enter the model input.
- Trace artifact format: versioned canonical JSON Lines. Firmware records compact fixed-size
  events into a bounded RAM ring buffer, and host tooling converts them to JSONL. UART is
  limited to low-rate status and collection output.
- Core v1 fault classes: lock-order deadlock, priority inversion, missed ISR notification,
  and missing mutex release. The missed-notification case keeps the ISR active but omits its
  task notification deterministically. Healthy controls are mandatory.
- Scope gate: implement and validate one deterministic instance of each core class first;
  expand to four variants per class (16 instances) only after the end-to-end path passes.
  The proposed 6×8 matrix is a stretch goal, not a blocker for the first publishable run.
- Primary runtime: Ollama with `qwen2.5-coder:14b`, with exact tag and digest pinned at setup.
  The client uses an OpenAI-compatible endpoint so llama.cpp can be a secondary runtime.
- No automatic patch application, proprietary traces, hardware-in-the-loop, RAG, dashboard,
  fine-tuning, or v2 agentic tooling in this project.

## 3. Ownership and separation of duties

| Area | Owner | Deliverable |
|---|---|---|
| Architecture, baseline, shared contracts, integration, README | Codex | Healthy firmware, runner interfaces, build/repro scripts, integration and release checks |
| FreeRTOS faults and embedded correctness | Claude | Fault variants, private labels, expected scheduler/resource behavior, trace realism audit |
| Local model bridge, scoring, metrics, narrative assets | Gemini | Ollama client, prompts, schema handling, evaluator, baselines/ablation, charts |
| Scope/design approval and final technical/publication review | Denis | Frozen decisions, hardware/model validation, fault realism approval, publication approval |

Separation rules:

1. Claude owns injection design and labels but does not own the scorer.
2. Gemini owns scoring but must not read injection implementation files.
3. The model receives exported evidence bundles only, never the repository.
4. Shared schemas are changed only through a recorded decision and version bump.
5. One owner edits a source file at a time; handoffs are committed to `docs/coordination/`.

## 4. Work packages and order

### P0 — Agreement and contracts — COMPLETE

- Freeze task map, priorities, resources, trace schema, evidence-pack schema, verdict schema,
  scoring rubric, and repository isolation policy.
- Create `DESIGN.md`, `INTERFACES.md`, `DECISIONS.md`, `STATUS.md`, and owner handoffs.
- Exit gate: all three models record `AGREE` or a concrete objection; Denis resolves every
  objection before P1/P2/P3 implementation.

### P1 — Healthy baseline (Codex)

- Build FreeRTOS for QEMU `mps2-an385` with four interacting tasks and UART output.
- Add deterministic case selection and a common runner (`scripts/run_case.sh <opaque-id>`).
- Exit gate: clean build, boot, forward progress, valid trace, repeatable run.

### P2 — Observability (Codex, with Claude embedded review)

- Versioned JSONL trace events for task switches, mutex/queue operations, notifications,
  ISR activity, progress counters, and relevant fault registers.
- Fixed-size RAM trace buffer plus UART artifact; watchdog snapshot/halt on no progress.
- Optional GDB task-table walker only after the core pipeline works; it is not a v1 blocker.
- Exit gate: healthy and intentionally stalled runs produce parseable, sufficient artifacts.

### P3 — Fault laboratory (Claude)

- Implement the four core classes using opaque, compile-time-selected variants.
- Include a healthy reference and, where technically meaningful, a mutex priority-inheritance
  reference run.
- Write private ground truth and expected evidence for every variant.
- Exit gate: each core fault reproduces deterministically and can be distinguished from the
  other classes using evidence that does not reveal its label.

### P4 — Local model bridge (Gemini; synthetic inputs first)

- Implement Ollama REST client, versioned prompt, strict diagnosis schema, one controlled retry,
  request/response logging, and runtime metric capture.
- Validate against synthetic evidence before firmware integration.
- Pin model tag/digest, context size, temperature, seed where supported, and hardware settings.
- Exit gate: synthetic packs yield schema-valid verdicts and repeated identical requests are
  byte-identical, or nondeterminism is documented before scoring.

### P5 — Reducer and end-to-end runner (Codex + Gemini interface review)

- Deterministic allowlist reducer: raw artifacts → evidence pack, with token/size budget and
  leakage checks.
- Resumable runner: build → QEMU → collect → reduce → query → store.
- Store raw artifacts, packs, verdicts, parameters, and hashes for audit.
- Exit gate: one command runs the core matrix unattended; reruns differ only where the model
  runtime has an explicitly documented nondeterminism.

### P6 — Evaluation (Gemini; Denis adjudicates reasoning)

- Score class, culprit task/object, evidence grounding, fix usefulness, schema validity,
  latency, and healthy false positives.
- Add deterministic wait-for-graph baseline first. Cloud comparison and raw-log/evidence-pack
  ablation are optional extensions.
- Keep scorer access separated from injection sources.
- Exit gate: results tables and raw machine-readable results reproduce from stored artifacts.

### P7 — Audit and publication (Codex assembles; Claude/Gemini review; Denis approves)

- Codex: README, pinned versions/hashes, reproduction instructions.
- Claude: FreeRTOS correctness and fault-claim audit.
- Gemini: metrics, charts, and model-claim audit.
- Denis: final post and publication decision.

## 5. Shared interfaces

`artifacts/<opaque_case>/` contains UART log, trace buffer dump, task metadata, and optional
fault-register/GDB artifacts. `evidence_pack.json` is the only model input. `verdict.json`
is the only scorer input from the model.

Trace events must include `schema_version`, monotonic timestamp, neutral execution context,
priority when applicable, event type, resource/IRQ when applicable, result/state, owner when
known, and progress counter when useful.

Proposed verdict shape:

```json
{
  "schema_version": "1.0",
  "prompt_version": "1",
  "failure_class": "DEADLOCK_LOCK_ORDER",
  "confidence": 0.0,
  "culprit_tasks": ["taskA", "taskB"],
  "culprit_objects": ["mtx1", "mtx2"],
  "evidence": ["neutral observation from the evidence pack"],
  "source_location_hint": "optional neutral location",
  "recommended_fix": "bounded corrective action",
  "additional_evidence_needed": []
}
```

Allowed classes are versioned and include `NONE` for the healthy control. The reducer must
reject forbidden strings/paths and must never emit case IDs, injection names, or labels.

## 6. Consensus conflict resolutions

| Topic | Proposals | Merged resolution |
|---|---|---|
| Scope | 4 classes vs 6 classes × 8 variants | Four core classes first; 16-instance expansion is the v1 target; 6×8 is stretch. |
| Trace | Human-readable key/value vs bracket text | Versioned JSONL machine contract; render readable text separately. |
| Runtime | Ollama/Qwen vs llama.cpp/gpt-oss | Ollama/Qwen is baseline because it matches the project objective; alternate server/model is optional. |
| P3 owner | Claude (embedded owner) vs Codex (variant automation) | Claude owns fault semantics/labels; Codex owns common build/run integration. |
| P5 owner | Gemini vs Claude/Codex | Codex owns deterministic reducer/runner integration; Gemini owns model client/prompt/scoring. |
| GDB walker | Required observability vs sprawl risk | Optional after core trace/watchdog; must not block first end-to-end result. |
| Determinism | QEMU record/replay vs `-icount` only | Attempt record/replay; Denis approves any downgrade before benchmark collection. |

These coordination resolutions are approved. Future disagreements go to `DECISIONS.md` with
evidence and do not change the frozen plan unless Denis approves them.

## 7. Communication protocol

Use the shared files under `docs/coordination/` as the durable channel. Every handoff records
owner, task, commit, files, commands, results, limitations, and requested next action. Status
updates must identify blockers and exact acceptance-gate evidence. Commit messages and exported
evidence must not reveal fault ground truth.

## 8. Immediate implementation actions

1. Codex Luna completes P1-T01 environment bootstrap, then starts the healthy baseline.
2. Gemini Luna creates and freezes schemas, prompts, configuration, and synthetic fixtures.
3. Claude Luna revises P3 specifications under section 10.4 and waits for baseline interfaces
   before integrating fault source.
4. Owners update handoffs at every synchronization gate; Sol reviews each completed gate.
5. No real model benchmark query occurs before preregistration and the temporal firewall.

## 9. Agreement record

Each model records a decision here per the P0 exit gate. Append without deleting prior entries.

### Claude

- Decision: **AGREE WITH CHANGES** (below). This resolves cleanly against the frozen
  determinism/blinding rules in my original `PLAN_claude.md` proposal — the record/replay
  fallback language in §2 and the neutral-identifier rule in §6 both carry those constraints
  forward correctly, and the ISR-priority-violation direction I originally proposed in
  `PLAN_claude.md` §3 (P3-C04) was stated backwards there; since that class is correctly
  deferred out of the v1 core set here, no correction to this document was needed — just a
  note for whoever specs it later (see below).
- Requested changes (small, additive, does not reopen scope already agreed above):
  1. **P2 GDB walker, if/when implemented:** FreeRTOS list internals (`xListEnd`, `pxIndex`,
     `listGET_OWNER_OF_NEXT_ENTRY`) are where confident-but-wrong pointer arithmetic hides —
     code that walks correctly on one build and silently misreports on another. Require a
     self-check that cross-validates the walked task count against
     `uxCurrentNumberOfTasks` before trusting any GDB-derived task table.
  2. **Priority-inversion reference config:** the P3 "mutex priority-inheritance reference run"
     needs `configUSE_MUTEXES == 1` and the *same* resource created via
     `xSemaphoreCreateMutex()` in the reference vs. `xSemaphoreCreateBinary()` in the fault
     variant — identical call sites otherwise, so the diff is purely the inheritance property.
     Worth pinning in the baseline `FreeRTOSConfig.h` now so P1 doesn't have to be revisited.
  3. **Future ISR-priority-violation class (not v1 core, flagging for whenever it's added):**
     the violation is an NVIC priority set *numerically lower* than
     `configMAX_SYSCALL_INTERRUPT_PRIORITY` (i.e. **higher** urgency — unmasked by kernel
     critical sections), not numerically above. Get the direction right at spec time; I had it
     backwards in my own draft.
  4. **Model pinning:** if Ollama stays primary runtime, pin by the digest `ollama show`
     reports for the pulled model, not just the mutable tag, so a re-pull can't silently change
     the model under test. This is the Ollama-equivalent of the GGUF SHA256 pinning already
     required by §2.
- No objection to: scope gate (4 classes → 16 instances → 6×8 stretch), Ollama-primary /
  llama.cpp-optional runtime choice, P3/P5 ownership split, or the JSONL trace format.
- Ready to start drafting the four P3 fault specifications and private-label format against
  this document once Codex and Gemini have also recorded a decision here.
- Signature/date: Claude, 2026-09-03


## 10. Approved Sol amendments — binding implementation rules

**Approved by Denis:** 2026-09-03  
**Implementation tier:** Luna  
**Review tier:** Sol at synchronization gates

This section incorporates `REVIEW_SOL.md`. Where an older statement in this plan or a handoff
conflicts with this section, this section controls.

### 10.1 Canonical task IDs and ownership

| ID | Deliverable | Owner |
|---|---|---|
| P0-T02 | Evidence-pack and verdict schemas plus synthetic fixtures | Gemini; Codex approves interface |
| P1-T01 | Environment bootstrap: Git, pinned FreeRTOS, compiler, QEMU, target capability check | Codex |
| P1-T02 | Healthy four-task firmware baseline | Codex |
| P1-T03 | Deterministic QEMU runner and replay capability test | Codex |
| P2-T01 | Compact RAM trace recorder and host JSONL conversion | Codex; Claude reviews |
| P2-T02 | Periodic progress monitor, snapshot, and host timeout | Codex; Claude reviews |
| P2-T03 | Artifact collector and optional validated GDB task walker | Codex; Claude reviews |
| P3-T01 | Four fault specifications and deterministic ordering | Claude |
| P3-T02 | Injection implementations and healthy/reference variants | Claude |
| P3-T03 | Private labels and expected evidence | Claude |
| P4-T01 | Ollama-compatible client and schema enforcement | Gemini |
| P4-T02 | Versioned prompt and inference configuration | Gemini |
| P4-T03 | Inference repeatability and resource metrics | Gemini |
| P5-T01 | Deterministic reducer and leakage checks | Codex |
| P5-T02 | Resumable end-to-end runner | Codex |
| P6-T01 | Scorer and result tables | Gemini |
| P6-T02 | Deterministic wait-for-graph baseline | Gemini |

Future status and handoff files use this map. Owners do not edit another owner area without a
recorded handoff.

### 10.2 Environment gate

P1-T01 blocks firmware claims. Before P1-T02 begins, initialize Git; install or locate and pin
`qemu-system-arm` and `arm-none-eabi-gcc`; pin the FreeRTOS source revision and hashes; record
licenses and exact versions; verify `mps2-an385`; and test the local support for `-icount` and
record/replay. The 2026-09-03 review found QEMU and the ARM compiler absent from `PATH`, and no
Git repository at the project root.

### 10.3 Blinding and temporal firewall

Gemini freezes and hashes schemas, prompt, inference parameters, and synthetic tests before
accessing private labels or real benchmark verdicts. Any later prompt, schema, reducer, model,
or context-selection change creates a new experiment version and invalidates prior aggregate
results until a complete rerun.

Codex develops the reducer without labels, friendly case mappings, or injection source. Claude
owns injections and labels but does not tune prompts or scoring. Gemini may read labels only
after the prompt freeze and may never read injection implementation source. The model receives
only the exported evidence pack and verdict schema.

### 10.4 Fault realism and collection

Fault ordering is deterministic by construction, using explicit gates or barriers instead of
arbitrary delays. The deadlock tasks both prove first-mutex ownership before requesting the
second mutex. The inversion case explicitly seeds its binary semaphore, forces the low-holder,
high-waiter, and medium-runner order, and records base plus effective priority.

The core `MISSED_ISR_NOTIFICATION` case uses a timer ISR that still fires and advances a neutral
counter while the faulty branch deterministically omits `xTaskNotifyFromISR()`. Invalid ISR API
use and notification-overwrite races are separate future classes.

An idle-hook-only watchdog is prohibited. A small highest-priority periodic monitor inspects
per-task progress counters and captures a snapshot; a host-side timeout is the final collection
guard. Monitor overhead is measured and reported.

### 10.5 Trace and evidence contracts

The bounded RAM event stream is authoritative. Each compact event has a monotonic sequence
number and neutral stable ID. Host tooling converts it to canonical versioned JSONL. UART carries
only low-rate status or collection data.

Evidence-pack events and source excerpts have stable neutral IDs. Verdict evidence is structured
as references plus claims, for example:

```json
"evidence": [
  {"ref": "evt-000123", "claim": "taskA waits for mtx2 while holding mtx1"}
]
```

Leakage checks inspect keys, values, metadata, paths, source excerpts, prompt logs, and errors.
A canary fixture containing forbidden markers must make export fail closed. If the optional GDB
walker is implemented, it cross-checks its task count against `uxCurrentNumberOfTasks`.

### 10.6 Determinism, preregistration, and scoring

Build, QEMU execution, and inference repeatability are tested and reported separately. Compare
at least one timing-sensitive case with and without the proposed `-icount shift=7` before
freezing it. If model output is not byte-identical, preregister repeated trials and report
variance rather than weakening the gate after results are seen.

Before any real model query, freeze and hash the case matrix, healthy-control count, repetitions,
prompt, model digest, parameters, schemas, reducer, token budget, metrics, retry policy, partial
credit, exclusion rules, and human-adjudication rubric.

Report class exact match, culprit task/object set scores, schema validity, evidence-reference
validity, and healthy false-positive rate separately. Fix quality and right-answer-for-the-right-
reason are blinded human judgments. Four variants per class support an engineering demonstration,
not broad statistical generalization.

### 10.7 Synchronization gates

Luna agents work in parallel and synchronize through `STATUS.md`, `DECISIONS.md`, and handoffs:

1. after schemas and synthetic fixtures freeze;
2. after environment bootstrap and healthy baseline boot;
3. after one validated instance of each fault class;
4. after the first complete evidence-to-verdict-to-score run;
5. before benchmark collection and before publication.

Sol reviews each gate and material dispute. Denis remains final authority.
