# Coordination decisions

| Date | Decision / proposal | Status | Authority |
|---|---|---|---|
| 2026-09-03 | Use `PLAN_MERGED.md` as the single coordination plan synthesized from the three proposals. | approved | Denis |
| 2026-09-03 | Start with four core fault classes and a healthy control; treat the larger 6×8 matrix as an expansion gate. | approved | Denis |
| 2026-09-03 | Use versioned JSONL traces and a blinded JSON evidence pack as the model boundary. | approved | Denis |
| 2026-09-03 | Keep fault semantics/labels with Claude, integration with Codex, and model/evaluation with Gemini. | approved | Denis |
| 2026-09-03 | Standardize failure_class enum: `DEADLOCK_LOCK_ORDER`, `PRIORITY_INVERSION`, `MISSED_ISR_NOTIFICATION`, `MISSING_MUTEX_RELEASE`, `NONE`. | approved | Consensus (Claude/Gemini/Codex) |
| 2026-09-03 | Runtime engine: **Ollama is PRIMARY** (`qwen2.5-coder:14b`), `llama-server` is secondary. `client.py` uses OpenAI-compatible `/v1/chat/completions` API to support both transparently via `--api-base`. | approved | Consensus (Denis/Gemini/Codex/Claude) |
| 2026-09-03 | Adopt the canonical task and ownership map in `PLAN_MERGED.md` section 10.1. | approved | Denis |
| 2026-09-03 | Add environment bootstrap as a blocking gate and validate QEMU determinism locally. | approved | Denis |
| 2026-09-03 | Freeze prompt, schemas, reducer, model configuration, and synthetic tests before label-based evaluation. | approved | Denis |
| 2026-09-03 | Use explicit fault-ordering gates and omitted ISR notification for the core missed-notification case. | approved | Denis |
| 2026-09-03 | Use a periodic monitor task plus host timeout; RAM events are authoritative and host-rendered as JSONL. | approved | Denis |
| 2026-09-03 | Add stable evidence references, fail-closed leakage canaries, and explicit access boundaries. | approved | Denis |
| 2026-09-03 | Preregister the matrix, repetitions, metrics, exclusions, versions, and adjudication before real model queries. | approved | Denis |
| 2026-09-03 | Use Luna for implementation and Sol for synchronization-gate architecture reviews. | approved | Denis |
