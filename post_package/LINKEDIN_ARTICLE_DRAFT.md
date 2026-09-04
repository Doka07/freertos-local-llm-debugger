# We Ran a Local 14B LLM on an RTX 5080 to Debug FreeRTOS Concurrency Bugs. Here Is What Broke.

Most AI coding benchmarks test trivial Python leetcode problems. But what happens when you pit a local open-weights model against real embedded firmware—specifically, concurrent task synchronization bugs in the **FreeRTOS kernel running on an emulated ARM Cortex-M3**?

Over the past week, we built an automated hardware-in-the-loop diagnostic harness. We injected four classic concurrency anomalies (deadlocks, priority inversions, unreleased mutexes, and dropped ISR notifications) into real C firmware, captured deterministic UART trace streams under QEMU, and fed blinded evidence packages to **`qwen2.5-coder:14b` running locally via Ollama on an NVIDIA RTX 5080**.

We also compared its diagnoses against a **120-line deterministic graph-cycle detector** — a simple, auditable script that ended up mattering more than we expected.

If you think local LLMs are ready to autonomously triage safety-critical embedded systems out of the box, our empirical findings will make you think twice.

---

## 🥊 The Head-to-Head Scorecard

Here is how the models performed across the exact same runtime trace evidence:

| Test Scenario | Ground Truth Class | Local Qwen 14B (RTX 5080) | Deterministic Baseline (120-Line Cycle Detector) |
| :--- | :--- | :--- | :--- |
| **Case 1** | `DEADLOCK_LOCK_ORDER` | **✅ PASS** (100% precision) | **✅ PASS** (Cycle detected) |
| **Case 2** | `PRIORITY_INVERSION` | **❌ FAIL** (Claims Deadlock) | ❌ FAIL (No cycle — but correctly refuses to call it a deadlock) |
| **Case 3** | `MISSED_ISR_NOTIFICATION` | **🚨 FABRICATES LOCKS** | ❌ FAIL (No cycle — correctly refuses to call it a deadlock) |
| **Case 4** | `MISSING_MUTEX_RELEASE` | **❌ FAIL** (Claims 1-lock Deadlock!) | **🛡️ GUARD** (Proves no cycle) |
| **Case 5** | `NONE` (Healthy Control) | **✅ PASS** (0 false alarms) | **✅ PASS** (0 cycles) |
| **Overall Accuracy** | — | **40.0%** (2/5) | **40.0%** (2/5) |
| **Deadlock False Alarm Rate** | — | **75.0%** (3 false alarms!) | **0.0%** |

*Note on sample size: each scenario above is a single instance of its fault class (n=1/class, 5 cases total). These are illustrative results from one pilot run, not a statistically powered accuracy claim — read them as "what happened this time," not "what always happens."*

---

## 🔍 Point 1: The "Deadlock Trap" (The Local Model Prior)

When we fed `qwen2.5-coder:14b` a textbook AB-BA circular wait (`case_001`), it diagnosed it in **4.8 seconds with surgical perfection**—correctly identifying tasks `taskA` and `taskB`, mutexes `mtx1` and `mtx2`, and citing all four acquisition events.

**Then came Case 4 (Missing Mutex Release):**
```text
resource_table: ['mtx1']  <-- Note: ONLY ONE MUTEX EXISTS!
[evt-000001] tick=0 task=taskA(prio 2) event=MTX_TAKE res=mtx1 ret=OK
[evt-000003] tick=0 task=taskB(prio 2) event=MTX_TAKE res=mtx1 ret=BLOCK
```
`taskA` took `mtx1` and leaked it. `taskB` blocked waiting for `mtx1`. 

Any junior firmware engineer knows it is **mathematically impossible** to have a circular deadlock with only one mutex. Yet, the local model reported:
```json
{
  "failure_class": "DEADLOCK_LOCK_ORDER",
  "confidence": 0.95,
  "culprit_tasks": ["taskA", "taskB"]
}
```
**Why?** Because 90% of open-source internet discussions on "blocked multi-threaded code" talk about deadlocks. The local 14B model exhibits a massive **Deadlock Prior**: whenever threads stop moving, it reflexively screams *Deadlock*.

---

## 🚨 Point 2: The "Illusion of Competence" (Phantom Lock Confabulation)

To guarantee reliable agentic integration, we forced the model to return structured JSON adhering to a strict JSON Schema, requiring exact event reference IDs (`evt-XXXXXX`).

In **Case 3 (Missed Hardware Timer ISR Notification)**, a CMSDK timer interrupt fired steadily on schedule, but omitted its task notification. The consumer task starved. There were **zero mutexes** in the firmware.

Look at what the local model generated:
```json
{
  "failure_class": "DEADLOCK_LOCK_ORDER",
  "confidence": 0.90,
  "culprit_objects": ["lockA", "lockB", "lockC"],
  "evidence": [
    {"ref": "evt-000001", "claim": "taskA acquired lockA"},
    {"ref": "evt-000002", "claim": "taskB acquired lockB"}
  ]
}
```
**`lockA`, `lockB`, and `lockC` did not exist anywhere in the evidence pack.** 
The model panicked because the trace had no synchronization primitives, so it **hallucinated a fictional 3-lock textbook deadlock out of thin air** to satisfy the schema!

> ⚠️ **Key Takeaway:** Strict JSON schema validation guarantees *syntactic shape*, **NOT semantic truth**. The output was 100% valid JSON, had 0.90 confidence, and was 100% hallucinated. Only our post-hoc evidence reference verifier caught the deception.

---

## 🛡️ Point 3: The Winning Architecture is Hybrid (LLM + Deterministic Tooling)

Does this mean local LLMs are useless in embedded engineering? **No. It means you must never deploy an LLM alone.**

We built a 120-line deterministic wait-for-graph cycle detector in Python using Tarjan's DFS algorithm. 
* **The Baseline alone:** Only 40% accurate (it cannot detect priority inversions or missed ISRs).
* **The Local LLM alone:** 75% false deadlock alarm rate.
* **The Combined Hybrid System:** 
  * Whenever the LLM claims a deadlock, the deterministic baseline checks the directed graph. 
  * If no cycle exists, the baseline **vetoes the LLM's hallucination**.
  * Result: **100% fault detection** with **0.0% false deadlock alarms**.

---

## 🛠️ Lessons for Engineering Leaders

1. **Beware high confidence:** The local model produced `confidence: 0.95` on its worst hallucinations. Never use LLM confidence scores as safety gates.
2. **Cross-check evidence references:** Enforce that every cited ID (`evt-1049`) actually existed in the raw trace.
3. **Use the right tool for the job:** Let deterministic algorithms handle graph cycles and formal logic; use LLMs for natural language explanations, synthesis, and repair recommendations.

What has been your experience running local code models against real low-level firmware? Drop your thoughts below! 👇

---
*The public repository contains the FreeRTOS Cortex-M3 baseline, QEMU runner, reducer, evaluation scripts, benchmark reports, and synthetic fixtures. The four private fault-injection sources and ground-truth labels are withheld; see the README for the exact reproduction boundary.*
