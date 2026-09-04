# FreeRTOS Local-LLM Debugging Project

## Coordination Plan — Draft 0.1

**Status:** Proposed for review; implementation must not begin until Denis, Codex, Claude, and Gemini record agreement.

**Project owner:** Denis Krutskih  
**Technical integration owner:** Codex  
**Embedded fault owner:** Claude  
**LLM experiment owner:** Gemini  
**Model under test:** Local Qwen through Ollama

---

## 1. Project objective

Build a reproducible demonstration in which firmware written in C runs FreeRTOS on an emulated Cortex-M target in QEMU. The firmware produces structured execution traces under both healthy and deliberately faulty conditions. A local open-weight Qwen model analyzes selected firmware source, configuration, and traces to identify the failure and propose a grounded fix.

The project must demonstrate engineering evidence, not merely an impressive model response. Diagnoses will be evaluated automatically against private ground truth and manually reviewed for FreeRTOS correctness.

Primary publication question:

> Can a local LLM diagnose injected FreeRTOS concurrency and interrupt failures from C source code and execution traces?

---

## 2. Hardware and intended environment

- Host OS: Ubuntu
- CPU: AMD Ryzen 9 9950X3D, 16 cores / 32 threads
- GPU: NVIDIA GeForce RTX 5080, 16 GB VRAM
- System RAM: 64 GB
- NVIDIA driver: 580.173.02
- CUDA capability reported by driver: 13.0
- Firmware language: C
- RTOS: FreeRTOS
- Emulation: QEMU, Cortex-M target
- Initial target candidate: ARM MPS2 AN385 / Cortex-M3
- Compiler candidate: Arm GNU Toolchain
- Local model runtime: Ollama
- Initial model candidate: Qwen 9B-class model
- Comparison model candidate: Qwen 30B/35B-class quantized or MoE model

Exact versions and model tags must be pinned during setup rather than assumed in this draft.

---

## 3. Participants and authority

### Denis — project owner and embedded engineering authority

Responsibilities:

- Approve scope, architecture, and publication claims.
- Validate whether task priorities, mutex use, interrupt behavior, and failure symptoms are technically credible.
- Resolve disagreements that cannot be settled by evidence or tests.
- Approve the final experiment and LinkedIn publication.

Denis does not need to perform routine integration work, but every material scope change requires his approval.

### Codex — technical lead and integration owner

Responsibilities:

- Establish repository layout and collaboration files.
- Implement the healthy FreeRTOS/QEMU baseline.
- Define shared firmware, trace, scenario, and result interfaces.
- Add build, run, lint, validation, and reproducibility scripts.
- Integrate contributions proposed by Claude and Gemini.
- Resolve code conflicts without silently changing an agreed interface.
- Run end-to-end verification and maintain the main README.
- Produce final release candidates for Denis.

Codex is the only default integration owner. This avoids multiple models independently rewriting shared architecture.

### Claude — embedded fault-injection owner

Responsibilities:

- Specify and implement the fault cases after shared interfaces are approved.
- Own the technical design of:
  - ABBA mutex deadlock
  - priority inversion
  - missing interrupt
  - missing mutex release on an error path
- Create corresponding healthy controls where needed.
- Document expected scheduler, mutex, and ISR behavior in private ground-truth files.
- Review traces for realism and answer leakage.
- Audit Qwen's proposed root causes and fixes for FreeRTOS correctness.

Claude must not change shared schemas or baseline architecture without submitting a decision proposal.

### Gemini — local-LLM experiment owner

Responsibilities:

- Implement the Python-to-Ollama interaction layer.
- Define prompt templates after input boundaries are approved.
- Implement context selection and sanitization.
- Define and validate the structured diagnosis schema.
- Implement experiment automation and result scoring.
- Collect latency, tokens-per-second, RAM, VRAM, and CPU metrics where practical.
- Produce result tables, charts, and candidate visual storytelling assets.
- Review whether published claims are supported by measured results.

Gemini must first develop against synthetic traces and must not depend on unfinished firmware.

### Local Qwen — model under test

Qwen is not an implementation participant. It performs blind diagnosis using only approved evidence packages.

Qwen must never receive:

- Injection implementation files
- Ground-truth files
- Revealing case names or paths
- Expected answers
- Review notes describing the fault
- Commit messages that disclose the injected issue

---

## 4. Scope for version 1

### Required capabilities

- Boot FreeRTOS firmware on Cortex-M under QEMU.
- Run a healthy multi-task application deterministically.
- Emit structured UART trace events.
- Monitor task progress, synchronization, and interrupt activity.
- Select a test case without revealing its identity to Qwen.
- Reproduce four injected failures:
  1. ABBA deadlock
  2. priority inversion
  3. missing interrupt
  4. missing mutex unlock
- Run a healthy negative-control case.
- Submit sanitized evidence to local Qwen through Ollama.
- Require schema-valid JSON diagnoses.
- Score diagnoses against private ground truth.
- Compare at least two local Qwen model sizes if time permits.
- Preserve all commands required to reproduce the experiment.

### Explicitly out of scope for version 1

- Running the LLM on the Cortex-M target
- Connecting the model to proprietary or workplace traces
- Automatic application of model-generated patches
- Giving Qwen unrestricted shell access
- Hardware-in-the-loop execution
- RAG/vector database unless simple context selection proves insufficient
- A graphical application or web dashboard
- Fine-tuning a model

---

## 5. Baseline firmware concept

The healthy application should contain realistic interacting tasks rather than isolated artificial snippets.

Candidate tasks:

| Task | Purpose |
|---|---|
| Producer | Generate simulated device or sensor data |
| Processor | Consume and transform data |
| Storage/logger | Record processed output |
| IRQ consumer | Wait for notification from an ISR |
| Health monitor | Detect stalled progress, missed interrupts, and timeouts |

The final priorities, periods, queues, and mutex relationships must be documented in an architecture decision before fault implementation begins.

---

## 6. Required fault cases

### Case A — ABBA deadlock

- Task A owns mutex 1 and waits for mutex 2.
- Task B owns mutex 2 and waits for mutex 1.
- The health monitor detects lack of forward progress.
- The trace exposes ownership and wait relationships without stating `deadlock`.

### Case B — priority inversion

- A low-priority task owns a resource needed by a high-priority task.
- A medium-priority CPU-bound task interferes with the low-priority task.
- The experiment must distinguish ordinary blocking from actual priority inversion.
- A comparison run should demonstrate the effect of correct FreeRTOS mutex priority inheritance where technically possible.

### Case C — missing interrupt

- A simulated peripheral reaches a data-ready or timer condition.
- Expected interrupt progress does not occur.
- Version 1 should use a deterministic cause, initially proposed as the interrupt not being enabled or the ISR notification being omitted.
- The final injected mechanism depends on what QEMU exposes reliably for the selected board.

### Case D — missing mutex unlock

- A task takes a mutex.
- An injected error path returns without releasing it.
- Another task blocks permanently.
- The evidence must allow the model to distinguish this from circular deadlock.

### Healthy control

- Uses equivalent workload without an injected defect.
- The model should return `no_failure_detected` or an explicitly uncertain result.
- False accusations in the healthy case count against the model.

---

## 7. Shared technical contracts

These contracts must be approved before parallel implementation.

### 7.1 Trace event format

Initial human-readable proposal:

```text
EVT ts=125 task=storage prio=1 action=MUTEX_WAIT resource=data_mutex owner=processor value=0
```

Required semantic fields:

- Monotonic timestamp
- Task or execution context
- Task priority when applicable
- Action/event type
- Resource or interrupt identity when applicable
- Result or state
- Owner when known
- Progress counter or observed value when useful

The implementation may emit JSON Lines instead if all participants agree before coding.

### 7.2 Scenario runner

Proposed external interface:

```bash
./scripts/run_case.sh case_001
```

The public case identifier must be opaque. Friendly names may exist only in private orchestration or ground-truth data.

### 7.3 Investigation command

Proposed interface:

```bash
python3 tools/investigate.py \
  --case artifacts/case_001 \
  --model qwen-model-tag
```

### 7.4 Diagnosis schema

Minimum proposed response:

```json
{
  "case_id": "case_001",
  "failure_class": "deadlock",
  "confidence": 0.94,
  "tasks": ["processor", "storage"],
  "resources": ["data_mutex", "log_mutex"],
  "evidence": ["specific trace or source observation"],
  "suspected_locations": ["processor.c:87"],
  "recommended_fix": "Use a consistent mutex acquisition order",
  "additional_evidence_needed": []
}
```

Allowed failure classes must be enumerated and versioned.

---

## 8. How the models communicate

There is no automatic shared memory, global variable, or direct model-to-model channel assumed by this project. Separate AI sessions do not reliably share conversational state.

The communication protocol is **file-based collaboration through a shared Git repository**.

### Source-of-truth files

```text
docs/coordination/
  PROJECT_PLAN.md
  STATUS.md
  DECISIONS.md
  INTERFACES.md
  REVIEWS.md
  CHANGELOG.md
  handoffs/
    codex.md
    claude.md
    gemini.md
```

Machine-readable state may additionally use:

```text
coordination/
  task_board.yaml
  interface_versions.json
```

### Communication rules

1. Every model reads this plan, `STATUS.md`, `DECISIONS.md`, and `INTERFACES.md` before proposing work.
2. A model writes only within its assigned ownership area unless explicitly handed another task.
3. A proposed interface change is recorded in `DECISIONS.md` before implementation.
4. Handoffs are written to the relevant file under `docs/coordination/handoffs/`.
5. Reviews identify exact files, commits, commands, and observed results.
6. No model may treat another model's chat response as authoritative unless it is copied into the repository.
7. Git commits provide change history; the files provide project memory.
8. Environment variables configure processes only. They must not store project decisions or coordination state.
9. Build artifacts and model outputs are never used as the only record of a decision.
10. Denis resolves unresolved scope or architecture disputes.

### Recommended handoff format

```markdown
## Handoff: <short title>

- Author: Claude | Codex | Gemini
- Date/time: ISO-8601
- Based on commit: <hash or "not committed">
- Task: <task ID>
- Status: proposed | ready-for-review | blocked | accepted
- Files changed: <paths>
- Commands run: <commands>
- Results: <concise evidence>
- Known limitations: <items>
- Requested next action: <specific owner and action>
```

### Git workflow

- Prefer one branch per owned work package.
- Codex integrates reviewed changes into the main branch.
- Never have two models edit the same source file concurrently.
- Rebase or merge only after checking the shared status files.
- Commit messages must not reveal fault ground truth in branches or histories accessible to Qwen's evidence collector.
- Qwen should analyze an exported evidence bundle, never the full Git repository.

---

## 9. Repository boundary and information isolation

Proposed layout:

```text
freertos-local-llm-debug/
  firmware/
    include/
    src/
    portable/
  experiment/
    injections/
    ground_truth/
  tools/
    collector/
    investigator/
    evaluator/
  prompts/
  schemas/
  scripts/
  tests/
  artifacts/
  docs/
    coordination/
  README.md
```

The evidence-packaging tool must use an explicit allowlist. It must never package the entire repository.

Candidate evidence bundle:

```text
evidence/case_001/
  trace.log
  FreeRTOSConfig.h
  task_map.json
  source_manifest.json
  source/
```

Before Qwen is invoked, a leakage test should reject evidence containing forbidden paths, friendly case names, expected classifications, or known injection markers.

---

## 10. Work packages and acceptance criteria

### WP0 — agreement and contracts

**Owner:** Codex coordinates; everyone reviews.

Deliverables:

- Approved plan
- Approved ownership
- Approved trace format
- Approved diagnosis schema
- Approved repository and isolation policy

Acceptance:

- Denis, Codex, Claude, and Gemini each record `AGREE`, `AGREE WITH CHANGES`, or `BLOCK` in Section 14.
- Every requested change is resolved in the plan or decisions file.

### WP1 — healthy FreeRTOS/QEMU baseline

**Owner:** Codex

Acceptance:

- Clean checkout builds using documented commands.
- QEMU boots the Cortex-M firmware.
- All baseline tasks make forward progress.
- UART trace validates against the agreed schema.
- Healthy run exits or is stopped deterministically with a passing result.

### WP2 — embedded fault laboratory

**Owner:** Claude

Acceptance:

- Four required faults reproduce deterministically.
- Each case has private ground truth.
- Each case has at least one appropriate healthy/reference run.
- Traces contain adequate evidence without explicit answer leakage.
- Codex can run every case through the common runner.

### WP3 — local model and investigator

**Owner:** Gemini

Acceptance:

- Ollama installation and verification are documented.
- The selected Qwen model uses the NVIDIA GPU as expected.
- A synthetic evidence bundle produces schema-valid output.
- Invalid model output is handled without silent data loss.
- Prompts and inference parameters are versioned.

### WP4 — evaluation and metrics

**Owner:** Gemini; reviewed by Codex and Claude

Acceptance:

- Evaluator compares results with ground truth.
- Healthy-case false positives are reported.
- Multiple runs can be executed with controlled inference parameters.
- Runtime and resource metrics are collected consistently.
- Raw results remain available for audit.

### WP5 — integration and reproducibility

**Owner:** Codex

Acceptance:

- One documented command runs the selected experiment suite.
- Evidence isolation checks pass.
- Automated tests pass.
- A new user can reproduce the baseline and at least one diagnosis from the README.

### WP6 — technical audit and publication

**Owners:** Claude audits embedded claims; Gemini audits data presentation; Codex assembles; Denis approves.

Acceptance:

- Claims match measured evidence.
- Limitations and model uncertainty are stated.
- No proprietary data, code, or traces are present.
- Repository and publication assets contain reproducibility details.

---

## 11. Proposed experiment matrix

For each model and failure case, test:

| Input mode | Contents |
|---|---|
| Trace only | Sanitized execution trace and task metadata |
| Source only | Selected C source and FreeRTOS configuration |
| Combined | Trace, source, configuration, and task metadata |
| Noisy combined | Combined input plus controlled irrelevant trace events |

Minimum metrics:

- Failure-class accuracy
- Task identification
- Resource/IRQ identification
- Evidence correctness
- Source-location usefulness
- Fix correctness
- Healthy-case false-positive rate
- Schema-valid response rate
- Analysis latency
- Host RAM and GPU VRAM use
- Token throughput if reliably available

The exact number of repetitions and scoring weights must be agreed before inspecting final model results.

---

## 12. Risks and controls

| Risk | Control |
|---|---|
| QEMU interrupt behavior differs from hardware | Document emulation boundary and validate IRQ mechanism independently |
| Priority inversion demonstration is technically weak | Define timing diagram and verify scheduler behavior before involving Qwen |
| Answer leakage | Allowlisted evidence bundles plus automated forbidden-term/path checks |
| Model guesses from case name | Use opaque identifiers and sanitized filenames |
| Nondeterministic scheduling | Fixed seeds, controlled timing, progress counters, repeated runs |
| Multiple AIs make conflicting edits | Explicit ownership, branches, handoffs, single integration owner |
| Prompt tuned to known answers | Freeze prompt and scoring before final evaluation |
| Local model hallucinates | Require cited evidence, confidence, healthy controls, and manual audit |
| Proprietary information enters project | Use only synthetic firmware and traces created for this project |
| Results overstate AI capability | Publish failure cases and limitations alongside successes |

---

## 13. Definition of done

Version 1 is complete when:

- All required FreeRTOS scenarios run reproducibly under QEMU.
- Qwen analyzes allowlisted evidence locally through Ollama.
- Diagnoses are stored as schema-valid, auditable results.
- Ground-truth scoring and healthy controls are included.
- At least the initial model is evaluated across all required cases.
- The larger comparison model is evaluated or explicitly deferred with a documented reason.
- Claude completes the embedded correctness audit.
- Gemini completes the evaluation/data audit.
- Codex completes integration and reproducibility verification.
- Denis approves the repository and publication claims.

---

## 14. Agreement record

Each participant should append a review without deleting earlier entries.

### Denis

- Decision: PENDING
- Requested changes:
- Signature/date:

### Codex

- Decision: PROPOSED BY CODEX; PENDING FINAL AGREEMENT
- Requested changes:
- Signature/date: 2026-09-03

### Claude

- Decision: PENDING
- Requested changes:
- Signature/date:

### Gemini

- Decision: PENDING
- Requested changes:
- Signature/date:

---

## 15. Immediate next step

1. Place this file in the shared project folder as `docs/coordination/PROJECT_PLAN.md`.
2. Ask Claude and Gemini to review the entire file.
3. Each participant updates Section 14 and lists concrete objections or changes.
4. Codex consolidates the feedback into Draft 0.2.
5. Denis approves the final division of work.
6. Only then create implementation tasks and begin WP1–WP3.

