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

## Benchmark results

The public benchmark record is in [publish/BENCHMARK_SUMMARY.md](publish/BENCHMARK_SUMMARY.md), [publish/EVALUATION_DATA.json](publish/EVALUATION_DATA.json), and [results_benchmark_run_v2.md](results_benchmark_run_v2.md). The current experiment contains one instance per class (`n=1/class`, five cases total), so it is illustrative rather than statistically powered.

| Case | Expected | Qwen 2.5 Coder 14B | Deterministic graph baseline |
|---|---|---|---|
| `case_001` | Deadlock lock order | Pass | Pass |
| `case_002` | Priority inversion | Grounded misclassification | No cycle / veto |
| `case_003` | Missed ISR notification | Unanchored confabulation | No cycle / veto |
| `case_004` | Missing mutex release | Grounded misclassification | No cycle / veto |
| `case_005` | Healthy control | Pass | Pass |

Headline results: Qwen fault-versus-healthy detection **100% (5/5)**, evidence grounding **80% (4/5)**, and deadlock false-alarm rate **75% (3/4 non-deadlock cases)**. The deterministic graph check caught every false deadlock claim in this run.

### Reproduce the benchmark

```bash
./scripts/check_env.sh
./scripts/build_baseline.sh
./scripts/run_case.sh case_001_deadlock
./scripts/run_case.sh case_002_priority_inversion
./scripts/run_case.sh case_003_missed_isr
./scripts/run_case.sh case_004_missing_release
./scripts/run_case.sh case_005_healthy
PYTHONPATH=. .venv/bin/python scripts/benchmark_v2.py
```

To regenerate the report from saved verdicts without new model calls:

```bash
PYTHONPATH=. .venv/bin/python scripts/benchmark_v2.py --reuse-verdicts
```

The recorded environment is FreeRTOS Kernel V11.3.1, QEMU 8.2.2, `arm-none-eabi-gcc` 13.2.1, Ollama v0.33.3, and `qwen2.5-coder:14b`. A clean public checkout can build the healthy baseline; reproducing the four injected fault cases and the original scored model run additionally requires the private injection/label package and local Ollama model. Raw `artifacts/`, ground-truth `labels/`, injected fault sources, build products, and local model data remain excluded to preserve the blinded evaluation boundary and avoid stale generated outputs. The committed reports and synthetic fixtures are the public benchmark record. See the publication files and coordination notes for limitations.

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
