# Suggested AI audit entries — Experiment 6

| Claim / generated output | Category | Verified? | How checked / next step |
|---|---|---|---|
| 2,790 hybrid configurations in Experiment 5E, 2,735 within latency ceiling, zero candidate flags | Numerical claim | Yes, file-level | Counted actual stage lengths from configs.json joined with ranking.csv in uploaded ZIP; check independently. Earlier response incorrectly gave 2,793 hybrids and wrong eligible standalone count. |
| GPU stage plan reflects actual calibrated stages | Code / methodology | Checked extraction | Used configs.json instead of historical names. Verify JSON against 5E data. |
| Benchmark command supports all three Argon2 variants, memory, passes, lanes, batch size and ns-per-hash | API | Documentation only | Upstream README documents flags. Actual executable, GPU device and current build compatibility pending. |
| Serial stage model is a real hybrid GPU measurement | Overclaim | False; explicitly not claimed | Only separate GPU stage timings; model sums times. No end-to-end hybrid GPU implementation. |
| GPU script parser and model work | Code | Local unit checks passed | Run --self-test; actual GPU backend unverified. Inspect raw logs, upstream tests and NVIDIA telemetry before reporting. |
| Negative result is sufficient to pass | Overclaim | Unverified | Rubric does not require positive result; professor decides whether novelty and contribution are adequate. |
