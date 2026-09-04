# PLAN_claude.md — RTOS Root-Cause Benchmark

**Author:** Claude (Opus 5)
**Status:** PROPOSAL — to be merged with `PLAN_chatgpt.md` and any other agent plans into `PLAN_MERGED.md`
**Owner / final arbiter:** Denis
**Date:** 2026-09-03

---

## 0. Read this first (instructions to Codex / Claude Code / Gemini)

You are one of several agents proposing a plan for the same project. Do **not** silently
overwrite this file. The merge protocol is in §9.

Three categories of content in this document:

- **[FROZEN]** — architectural decisions. Do not renegotiate. If you believe one is wrong,
  write your objection into §10 (Open Questions) with a concrete alternative and let Denis decide.
- **[PROPOSED]** — defaults that are reasonable but arguable. Argue in §10.
- **[OPEN]** — deliberately unresolved. Agents should propose answers.

Every work item has a stable ID (`P1-T02`). Use these IDs in the merged plan, in branch names,
and in commit messages so ownership stays traceable across agents.

---

## 1. What this project is

A **measured benchmark**, not a demo.

We inject known faults into a FreeRTOS application running on QEMU (Cortex-M3), collect
firmware artifacts deterministically, reduce them to a blind evidence pack, and ask a locally
hosted LLM to identify the root cause. We then score accuracy per fault class against ground
truth, with deterministic and cloud-model baselines.

The deliverable is a public repo plus a LinkedIn write-up reporting **accuracy numbers,
including the failures**. This is post #2 in a series; post #1 was a C-vs-Rust footprint and
latency study on Zephyr.

### Explicit non-goals

- Not an "AI debugs your firmware" demo.
- Not a claim that LLMs replace deterministic analysis. We expect to publish at least one
  class where a 150-line script beats the model, and that result stays in the post.
- No proprietary or employer-derived code, traces, or methodology. FreeRTOS upstream +
  original work only, on Denis's personal hardware.

### Success criteria

The project ships when we can state, with a reproducible repo behind it:

> "Across N fault instances in M classes, model X identified the root cause class correctly
> in A% of cases, identified the correct culprit objects in B% of cases, and produced a
> confident wrong answer in C% of cases. Deterministic baseline scored D%. Ablation without
> the evidence pack scored E%."

---

## 2. [FROZEN] Architecture

The model does **not** drive the firmware in v1. It is a pure function from a JSON document
to a JSON document.

```
FreeRTOS app + injected fault
      │  (build variant)
      ▼
QEMU mps2-an385, -icount, record/replay      ← determinism boundary
      │
      ▼
raw artifacts/                               ← UART log, trace ring buffer dump,
      │                                         fault frame, GDB task table
      ▼
reducer.py    [deterministic, NO LLM]
      │
      ▼
evidence_pack.json  (~2-4K tokens, blind)    ← blinding boundary
      │
      ▼
llama-server (local, temp=0, fixed seed, JSON schema enforced)
      │
      ▼
verdict.json
      │
      ▼
scorer.py  vs  labels/                       ← scorer never sees injection sources
```

**Rationale for keeping the model out of the loop in v1:** an agent with GDB access produces
an unfalsifiable trace of activity. A one-shot function produces a number. We need the number
first, because v2 (agentic, §8) is only interesting *relative to* v1.

### [FROZEN] Blinding rules

Violating any of these silently invalidates the entire result set.

1. Identifiers are neutral and **identical across all variants**: `taskA`..`taskD`, `mtx1`,
   `mtx2`, `q1`, `sem1`. Never `deadlock_task`, `bad_isr`, `victim`.
2. No comment in injected code names or hints at the bug.
3. `reducer.py` never emits: the variant ID, the injection macro name, build flags,
   file paths from the source tree, or `#ifdef` names.
4. `labels/` is excluded from the context of any agent working on P2, P3 (injection side),
   or P5. Add it to `.aiignore` / agent config, not just `.gitignore`.
5. The agent that writes the injections (P3) does **not** write the scorer (P6).
   Different agent, enforced.

### [FROZEN] Determinism rules

- QEMU runs with `-icount shift=7`. No wall-clock dependence anywhere.
- `--temp 0`, fixed `--seed`, pinned GGUF SHA256, pinned `--ctx-size` and KV cache type.
- Gate: submitting the same evidence pack twice must return byte-identical JSON.
  If it does not, stop and fix before collecting any data.
- Gate: replaying the same recording twice must produce byte-identical UART output.

---

## 3. Phases and task IDs

Owner column is **[PROPOSED]** — agents may reassign in the merge, subject to the
separation-of-duties rule in §2.

### P0 — Design freeze (Denis, ~1h, blocks everything)

| ID | Task | Owner |
|---|---|---|
| P0-T01 | Task set: 4 tasks (sensor producer, processing, comms, logger), priorities, shared `mtx1`/`mtx2`/`q1` | Denis |
| P0-T02 | **Evidence pack JSON schema** — core IP of the project | Denis + agent draft |
| P0-T03 | Verdict JSON schema | Denis + agent draft |
| P0-T04 | Scoring rubric — decided *before* any model output is seen | Denis |
| P0-T05 | `DESIGN.md` written and frozen | Denis |

### P1 — FreeRTOS baseline on QEMU

| ID | Task | Owner |
|---|---|---|
| P1-T01 | FreeRTOS + CMake skeleton, `qemu-system-arm -machine mps2-an385 -nographic` boots 4 tasks, UART output, clean exit on magic value | Claude Code |
| P1-T02 | `-icount shift=7` integration | Claude Code |
| P1-T03 | `rr=record` / `rr=replay` round-trip verified | Claude Code |

**Exit gate:** two consecutive replays of one recording produce identical logs.
If record/replay does not work on the installed QEMU build, escalate immediately —
the determinism claim in §2 depends on it. Fallback in §10-Q3.

### P2 — Observability layer

Split by file to avoid git collisions. These are independent.

| ID | Task | Owner |
|---|---|---|
| P2-T01 | `trace_hooks.h` + `trace_buf.c` — `traceTASK_SWITCHED_IN`, `traceMOVED_TASK_TO_READY_STATE`, `traceTAKE_MUTEX_BLOCK`, `traceBLOCKING_ON_QUEUE_RECEIVE`, `traceQUEUE_SEND`; fixed 1024-entry RAM ring buffer | Codex |
| P2-T02 | `fault_dump.c` — HardFault handler: stacked frame, CFSR/HFSR/MMFAR/BFAR, `pxCurrentTCB`, parseable UART dump | Claude Code |
| P2-T03 | `watchdog.c` — idle-hook progress watchdog, snapshot + halt after N ms of no forward progress (required to get artifacts out of a hang) | Codex |
| P2-T04 | `tools/gdb_tasks.py` — GDB Python walker over `pxReadyTasksLists`, `xDelayedTaskList1/2`, `xSuspendedTaskList`; emits task table with state, priority, base priority, stack high-water, PC | Claude Code → **line-by-line human review** |

**P2-T04 warning to whoever takes it:** FreeRTOS list internals (`xListEnd`, `pxIndex`,
`listGET_OWNER_OF_NEXT_ENTRY`) are where confident-but-wrong pointer arithmetic hides —
code that works on one build and silently misreports on another. Include a self-check that
cross-validates task count against `uxCurrentNumberOfTasks`.

**Timebox:** P2 is the sprawl risk. If P2-T04 is not producing a correct table after one full
working day, drop stack high-water and `xTasksWaitingTermination` and ship reduced.

### P3 — Fault injection matrix

6 classes × 8 variants = **48 instances**. Variants differ in timing, task pair, and resource —
never in the nature of the bug.

| ID | Class | Injection |
|---|---|---|
| P3-C01 | `DEADLOCK_LOCK_ORDER` | taskA: mtx1→mtx2; taskB: mtx2→mtx1 |
| P3-C02 | `PRIORITY_INVERSION` | `xSemaphoreCreateBinary()` in place of `xSemaphoreCreateMutex()` — identical call sites, inheritance silently gone |
| P3-C03 | `ISR_BLOCKING_API` | `xQueueSend` instead of `xQueueSendFromISR` from a timer ISR |
| P3-C04 | `ISR_PRIORITY_VIOLATION` | NVIC priority numerically above `configMAX_SYSCALL_INTERRUPT_PRIORITY` — evidence is a register value, not a log line |
| P3-C05 | `STACK_OVERFLOW` | oversized local / recursion, `configCHECK_FOR_STACK_OVERFLOW=2` |
| P3-C06 | `STARVATION_MISSED_GIVE` | conditional skip of `xSemaphoreGive` on an error path |

| ID | Task | Owner |
|---|---|---|
| P3-T01 | Injection mechanism (compile-time variant selection, one build per instance) | Codex |
| P3-T02 | 48 variants generated | Codex |
| P3-T03 | `labels/<variant>.json` ground truth, written by the same agent as T02, which is then **done with this project area** | Codex |
| P3-T04 | Realism review — all 48 opened and confirmed to look like bugs a real team would ship | Denis |

P3-C04 is the class we most want to see the outcome of: the evidence is a numeric register
comparison, and no deterministic baseline we plan to write covers it.

### P4 — Local model serving (Denis, ~90 min, not delegated)

Environment-specific GPU work; agents are poor at this.

| ID | Task |
|---|---|
| P4-T01 | Move display to iGPU (or stop the display manager for runs). Verify `nvidia-smi` shows ~0MiB used before benchmarking. **Blocks everything else in P4.** |
| P4-T02 | Build llama.cpp: `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120` (RTX 5080 / sm_120) |
| P4-T03 | Pull `gpt-oss-20b` MXFP4, record SHA256 in `DESIGN.md` |
| P4-T04 | Commit `scripts/serve.sh` — no hand-typed launch commands ever |
| P4-T05 | Determinism gate: same pack twice → byte-identical JSON |
| P4-T06 | Secondary model `qwen3-coder:30b` via `--n-cpu-moe N`, tuned to ~15GB VRAM (partial expert offload, not all-or-nothing `--cpu-moe`) |

Reference launch (adjust in `serve.sh`, not here):

```
llama-server -m models/gpt-oss-20b-mxfp4.gguf \
  --ctx-size 65536 --cache-type-k q8_0 --cache-type-v q8_0 \
  -fa -ngl 99 -t 16 --temp 0 --seed 42 --port 8080
```

Hardware context: RTX 5080 16GB (Blackwell, MXFP4 native), Ryzen 9 9950X3D2 16C/32T,
60GB RAM. Use `-t 16`, not 32 — the extra SMT threads do not help expert offload.

### P5 — Bridge: reducer, prompt, client

Agent working this area is **denied access to `labels/` and to `src/injections/`**.

| ID | Task | Owner |
|---|---|---|
| P5-T01 | `reducer.py` — raw artifacts → evidence pack. Pure deterministic Python, zero LLM. Task table, lock ownership graph, wait-for edges, last-N trace events per task, fault registers. Emits token count, hard-fails over budget. | Claude Code |
| P5-T02 | `client.py` — POST to llama-server with enforced JSON schema, one retry on schema violation, full request/response logging | Claude Code |
| P5-T03 | `runner.py` — per variant: build → QEMU → collect → reduce → query → store. Resumable. | Claude Code |
| P5-T04 | Prompt template, versioned; prompt changes invalidate prior results and must bump a version field in `verdict.json` | Claude Code |

**Exit gate:** `./run_all.sh` produces 48 verdicts unattended; two full runs diff to zero.

### P6 — Scoring, baselines, ablation

Different agent from P3. May read `labels/`; may **not** read `src/injections/`.

| ID | Task | Owner |
|---|---|---|
| P6-T01 | `scorer.py` — per-class accuracy, confusion matrix | Gemini |
| P6-T02 | "Right answer, wrong reasoning" adjudication across all 48 — **manual, Denis** | Denis |
| P6-T03 | Baseline A: deterministic wait-for-graph deadlock detector (~150 LOC) on the same evidence packs. Expected to beat the model on P3-C01. Publish that. | Gemini |
| P6-T04 | Baseline B: same packs to a frontier cloud model — quantifies the cost of "local" | Gemini |
| P6-T05 | Ablation: raw log vs evidence pack, `gpt-oss-20b` only. One column, biggest talking point. | Gemini |
| P6-T06 | Results tables + charts | Gemini |

### P7 — Write-up

| ID | Task | Owner |
|---|---|---|
| P7-T01 | Draft | **Denis writes it.** Ghostwritten honest-measurement posts read exactly like ghostwritten honest-measurement posts, and this audience notices. |
| P7-T02 | Edit, tighten, check every claim against `results/` | Claude |
| P7-T03 | Repo README, reproduction instructions, version/hash pinning table | Codex |

---

## 4. Sequencing

```
P0 ──► P1 ──► P2 ──┐
                   ├──► P5 ──► P6 ──► P7
       P3 ─────────┘
P4 ── (parallel with P2, independent)
```

- P1 and P2 are strictly serial.
- P3 and P5 are parallel: different subtrees, no collisions.
- P4 has no dependency on firmware work at all — run it during a long P2 agent session.
- P6 requires P3 and P5 complete.

**Indicative calendar (weekends):** W1 = P0–P2 · W2 = P3–P4 · W3 = P5 + first full run ·
W4 = P6 + write-up.

---

## 5. Interface contracts

These are the seams between agents. Whoever owns the producing task owns the contract;
consumers code against it and do not modify it unilaterally.

- `artifacts/<variant>/` → produced by P1/P2, consumed by P5-T01
- `evidence_pack.json` → produced by P5-T01, consumed by P5-T02 (schema owner: P0-T02)
- `verdict.json` → produced by P5-T02, consumed by P6-T01 (schema owner: P0-T03)
- `labels/<variant>.json` → produced by P3-T03, consumed by P6-T01 only

Proposed verdict shape **[PROPOSED]**:

```json
{
  "schema_version": "1.0",
  "prompt_version": "3",
  "root_cause_class": "DEADLOCK_LOCK_ORDER",
  "culprit_tasks": ["taskA", "taskB"],
  "culprit_objects": ["mtx1", "mtx2"],
  "evidence": ["...", "..."],
  "confidence": 0.0
}
```

The `evidence` array is what lets P6-T02 separate *right answer* from *right answer for the
right reason* — the most quotable number in the write-up. Do not drop it.

---

## 6. Repo layout [PROPOSED]

```
/DESIGN.md              frozen decisions, hashes, versions
/PLAN_MERGED.md         the agreed plan (this file is only an input)
/firmware/              FreeRTOS app, trace hooks, fault dump, watchdog
/firmware/injections/   variant sources          [P5, P6 agents: no access]
/tools/gdb_tasks.py
/pipeline/              reducer.py, client.py, runner.py, prompts/
/labels/                ground truth             [P2, P3-inject, P5 agents: no access]
/baselines/             wait-for-graph detector, cloud client
/results/               verdicts, scores, tables
/scripts/               serve.sh, run_all.sh
```

---

## 7. Working agreements for agents

- One task ID per branch: `p2-t04-gdb-task-walker`. One task ID per PR.
- Commit messages start with the ID: `P2-T04: walk xSuspendedTaskList`.
- Do not edit files outside your task's declared subtree. If you need a change elsewhere,
  open an item in §10 instead of making it.
- Do not modify `DESIGN.md` — propose changes in §10.
- Every deliverable states its exit gate and is not "done" until the gate passes.
- If a gate cannot be met, escalate. Do not weaken the gate to pass it.
- No agent may both create ground truth and evaluate against it (§2, frozen).

---

## 8. v2 / post #3 — explicitly out of scope here

The agentic version: the model gets a restricted read-only tool surface against a **frozen
replayed core** (record/replay is what makes it reproducible), hard-capped at ~10 calls:
`list_tasks`, `backtrace(task)`, `read_var(symbol)`, `read_mem(addr,len)`,
`trace_tail(task,n)`, `nvic_config()`.

Headline question for that post: *does an agent that can query beat a one-shot model given a
well-built evidence pack?* Prediction — on these six classes the evidence pack wins and the
tool loop mostly burns tokens rediscovering it. If that holds, it is a more interesting result
than the reverse, and it needs v1's numbers to exist first.

Do not start v2 work under this plan.

---

## 9. Merge protocol with `PLAN_chatgpt.md` (and any other plan)

Each agent, in one pass, produces `PLAN_MERGED.md` containing:

1. **Union of scope** — any phase present in one plan and absent in another is listed, with a
   one-line argument for inclusion or exclusion. Nothing is dropped silently.
2. **Conflicts table** — for each disagreement: the two positions, the tradeoff, and a
   recommendation. Denis decides; the decision is recorded in §11 with a date.
3. **Single task ID space** — reuse `Pn-Tnn` where the tasks correspond; assign new IDs for
   genuinely new work. Note the source plan for each ID.
4. **Ownership assignment** honouring the separation-of-duties rule.

Anything marked **[FROZEN]** in §2 of this document survives the merge unless Denis
explicitly overrides it in §11. Everything else is negotiable.

---

## 10. Open questions

| # | Question | Raised by | Status |
|---|---|---|---|
| Q1 | 6×8 or 5×10? Fewer classes with more variants gives tighter per-class confidence intervals; more classes gives a richer failure taxonomy. | Claude | open |
| Q2 | Evidence pack token budget — 2K, 4K, or "as large as it needs to be"? Affects P5-T01's hard-fail threshold and the ablation design. | Claude | open |
| Q3 | Fallback if QEMU record/replay is unusable on the installed build: `-icount` alone plus a fixed RNG seed is *mostly* deterministic. Acceptable, or blocker? | Claude | open |
| Q4 | Does `-icount` distort the timing-sensitive classes (C02, C04) enough to make them unrealistic? | Claude | open |
| Q5 | Is `gpt-oss-20b` the headline model, or is the headline "two models compared"? Affects scope of P4-T06 significantly. | Claude | open |
| Q6 | Do we publish the evidence packs themselves in the repo? Strong for reproducibility; makes the benchmark trivially trainable-on later. | Claude | open |

Agents: append your own questions here rather than resolving them unilaterally.

---

## 11. Decision log

| Date | Decision | Decided by |
|---|---|---|
| 2026-09-03 | Benchmark framing, not demo. Model is a pure JSON→JSON function in v1. | Denis |
| 2026-09-03 | FreeRTOS on QEMU `mps2-an385`, not Zephyr. | Denis |
| | | |
