# Technical Post Plan: Autonomous RTOS Trace Debugging via Local LLM & QEMU

**Target System:** FreeRTOS on ARM Cortex-M (QEMU `mps2-an385` / `lm3s6965evb`)  
**Diagnostic Stack:** Local LLM via Ollama (`qwen2.5-coder:14b` / `deepseek-r1:8b`) + Python Async Watchdog Bridge  
**Multi-Agent Alignment Target:** Gemini (System & Integration Lead), Claude Code (Firmware & C Specialist), OpenAI Codex (Python Harness & Automation Specialist)

---

## 1. Executive Summary & Objective

Develop and document an automated, reproducible firmware triage pipeline where a local LLM acts as an autonomous embedded systems diagnostic engine.

The system will:
1. Emulate an ARM Cortex-M target running FreeRTOS on QEMU.
2. Inject classic, deterministic embedded concurrency and hardware synchronization faults (AB-BA Deadlock, Unbounded Priority Inversion, Missed ISR Notifications/Race Conditions).
3. Stream structured FreeRTOS kernel execution traces over emulated UART.
4. Catch execution hangs/anomalies via an automated Python harness.
5. Ingest and parse traces with a local Ollama model to pinpoint the root cause, identify the circular dependency / lock contention graph, and output a corrective patch.

---

## 2. Multi-Agent Task Division & Ownership

| Component / Layer | Primary Owner | Responsibilities & Deliverables |
| :--- | :--- | :--- |
| **Firmware & RTOS Core** | **Claude Code** | • FreeRTOS Cortex-M board port on QEMU (`mps2-an385` or `lm3s6965evb`).<br>• Structured trace emission engine (`[TS][TASK][PRIO][EVENT][RESOURCE][RET]`).<br>• Fault injection scenarios: AB-BA deadlock, Priority Inversion, Missed ISR/critical section overrun.<br>• CMake / Makefile build system targeting `arm-none-eabi-gcc`. |
| **Python Harness & Watchdog** | **OpenAI Codex** | • Async QEMU process manager & UART pipe reader.<br>• RTOS stall & anomaly detection engine (heartbeat timeout, assert trap, circular wait heuristics).<br>• Ollama REST client (`/api/chat` / `/api/generate`) with schema validation (JSON output).<br>• Benchmark script: Run $N$ iterations and evaluate LLM diagnosis accuracy across models. |
| **System Architecture & Narrative** | **Gemini** | • End-to-end integration protocol & unified schema definition.<br>• Ollama `Modelfile` and specialized system prompt engineering for RTOS state tracking.<br>• Blog post outline, technical narrative, architectural diagrams, and publication assets. |
| **Execution & Validation** | **Human Engineer** | • Run local hardware/QEMU pipeline on Linux workstation.<br>• Verify Ollama inference latency and VRAM footprint.<br>• Validate correctness of AI-generated fixes on running firmware. |

---

## 3. Firmware Architecture & Fault Injection Specifications

### 3.1 Trace Event Format (UART Protocol)
To ensure high-precision tokenization by local LLMs without token bloat:
```text
[T:<ms_tick>] [TSK:<task_name>] [P:<prio>] [EVT:<OP>] [RES:<res_id>] [RET:<status>]
```
* **OPs:** `MUTEX_TAKE`, `MUTEX_GIVE`, `SEMA_TAKE`, `SEMA_GIVE`, `NOTIFY_WAIT`, `NOTIFY_SEND_ISR`, `CTX_SWITCH`, `ENTER_CRITICAL`, `EXIT_CRITICAL`.
* **STATUS:** `OK`, `PENDING`, `TIMEOUT`, `ISR_BLOCKED`.

### 3.2 Injected Fault Scenarios

#### Scenario 1: Deterministic AB-BA Deadlock
* **Task A (Prio 2):** Takes `Mutex_SPI`, yields/delays 5ms, requests `Mutex_I2C`.
* **Task B (Prio 2):** Takes `Mutex_I2C`, yields/delays 5ms, requests `Mutex_SPI`.
* **Expected Failure:** Both tasks enter `Blocked` state (`portMAX_DELAY`). Scheduler falls through to `vApplicationIdleHook`.
* **LLM Success Metric:** Identify circular dependency: `Task_A -> Mutex_SPI -> Task_B -> Mutex_I2C -> Task_A`.

#### Scenario 2: Unbounded Priority Inversion
* **Task Low (Prio 1):** Takes standard binary semaphore / non-inheriting mutex guarding shared telemetry buffer.
* **Task High (Prio 3):** Wakes on timer, attempts to acquire the same mutex, blocks.
* **Task Med (Prio 2):** Heavy compute task wakes, preempts Task Low indefinitely.
* **Expected Failure:** Task High starves despite having highest priority; priority inheritance disabled.
* **LLM Success Metric:** Detect missing priority inheritance (`configUSE_MUTEXES = 1` vs `vSemaphoreCreateBinary`) and identify Task Med starvation impact.

#### Scenario 3: Missed ISR Event / Overwritten Notification
* **Timer/DMA ISR:** Emitted at high frequency via `xTaskNotifyFromISR()` with action `eSetValueWithoutOverwrite` or direct queue send with 0 timeout.
* **Task Consumer (Prio 2):** Enters an overly long critical section (`taskENTER_CRITICAL()`) or slow memory copy.
* **Expected Failure:** ISR fails to deliver event (`errQUEUE_FULL` / notification discarded); consumer enters indefinite wait on next loop.
* **LLM Success Metric:** Correlate ISR emission count with task consumption count and flag critical section duration violating interrupt rate.

---

## 4. Local Model Configuration & Harness Specs

### 4.1 Recommended Models
* **Primary Target:** `qwen2.5-coder:14b` (Optimal balance of code comprehension and causal inference).
* **Chain-of-Thought Alternative:** `deepseek-r1:8b` or `deepseek-r1:14b` (Strongest multi-step lock graph reasoning).
* **Lightweight Baseline:** `qwen2.5-coder:7b` (For rapid testing).

### 4.2 Ollama Runtime Parameters
* Context Window: `num_ctx 32768` (Prevents context truncation on long trace dumps).
* Temperature: `0.1` (Strict deterministic root-cause diagnosis).

### 4.3 Structured JSON Output Target
The Python harness will enforce structured output from Ollama:
```json
{
  "fault_detected": "DEADLOCK | PRIORITY_INVERSION | MISSED_ISR | NONE",
  "root_cause": "Detailed explanation of sequence of events",
  "culprit_tasks": ["TaskA", "TaskB"],
  "contested_primitives": ["Mutex_SPI", "Mutex_I2C"],
  "source_location_hint": "main.c: lines 84-112",
  "recommended_fix": "Description of code or configuration modification"
}
```

---

## 5. End-to-End Execution Flow

```
[Start QEMU Subprocess]
       │
       ▼
[Stream UART Trace to RingBuffer (Last 200 lines)]
       │
       ▼
[Heartbeat Monitor: Did task switch occur within 1500ms?]
       ├── Yes ──► Continue streaming
       └── No (Stall Detected!)
             │
             ▼
      [Capture Frozen Trace Snapshot]
             │
             ▼
      [Dispatch POST to Ollama /api/chat]
             │
             ▼
      [Extract JSON Root-Cause & Dependency Graph]
             │
             ▼
      [Output Terminal Report & Suggest C Diff]
```

---

## 6. Implementation Roadmap & Milestones

1. **Milestone 1: Firmware Skeleton (Claude Code)**
   - Minimal FreeRTOS port compiling with `arm-none-eabi-gcc`.
   - Running in `qemu-system-arm` with UART stdout.
2. **Milestone 2: Fault Matrix & Logging (Claude Code & Gemini)**
   - Implement Scenarios 1, 2, and 3 selectable via build flags (`-DFAULT_SCENARIO=1`).
   - Implement standardized trace macro wrapper `TRACE_LOG(...)`.
3. **Milestone 3: Python Watchdog & Ollama Bridge (Codex)**
   - `watchdog.py`: Subprocess runner, circular buffer, timeout trip logic, Ollama API connector.
4. **Milestone 4: Validation & Tuning (All Agents + Human)**
   - Benchmark 7B vs 14B vs DeepSeek-R1 accuracy on all 3 scenarios.
5. **Milestone 5: Technical Post & Repository Package (Gemini)**
   - Comprehensive blog post, clean GitHub README, ASCII state diagrams, and step-by-step reproduction instructions.
