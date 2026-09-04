# FreeRTOS Local LLM Debugger

A reproducible research prototype for debugging FreeRTOS failures with local language models and deterministic runtime evidence.

The project builds a Cortex-M3 FreeRTOS target, runs it under QEMU, reduces UART trace output into structured evidence packs, and evaluates a local Qwen model against deterministic wait-for-graph checks.

## Included

- FreeRTOS V11.3.1 baseline firmware for QEMU `mps2-an385`
- Deterministic trace capture and evidence reduction
- JSON schemas for evidence packs and model verdicts
- Synthetic fixtures and schema/scorer tests
- Qwen/Ollama client and benchmark tooling
- Deterministic Tarjan/DFS wait-for-graph baseline
- Benchmark reports and an article draft in `publish/`

## Quick start

```bash
./scripts/check_env.sh
./scripts/build_baseline.sh
./scripts/run_case.sh case_005_healthy
PYTHONPATH=. .venv/bin/pytest -q tests/
```

For local model evaluation, install Ollama separately, pull the model specified by the benchmark configuration, and run:

```bash
PYTHONPATH=. .venv/bin/python scripts/benchmark_v2.py
```

Use `--reuse-verdicts` to regenerate reports from saved verdicts without making new model calls.

## Reproducibility and scope

The benchmark currently contains one instance per fault class (`n=1/class`); results are a demonstration, not a statistically powered evaluation. See `publish/BENCHMARK_SUMMARY.md` and `results_benchmark_run_v2.md` for metrics, limitations, and comparative analysis.

Private fault-injection sources and ground-truth labels are intentionally excluded by `.gitignore` from a public repository to preserve blinding. Coordination records in `docs/coordination/` describe the experiment and review decisions.

## Layout

```text
firmware/     FreeRTOS target and trace instrumentation
pipeline/     Evidence reduction and local-model client
evaluation/   Scoring and deterministic baselines
schemas/      Frozen JSON interfaces
scripts/      Build, run, and benchmark commands
tests/        Automated validation
publish/      Benchmark summary and article draft
```
