# Experiment 7 — Result checking

This is a confirmatory rerun, not a new algorithm or another parameter search. The selection is frozen from the uploaded `exp7_full.zip` screening results. Copy the four files in this package into your **existing `exp7_stacking` directory**, next to `exp7_stacking.py`, `extra_kdfs.py`, `exp5c_global.py` and `exp5b_core.py`. Do not replace your compiled `native/` directory or your virtual environment. Use the same WSL environment as Experiment 7. No new dependencies should be needed (NumPy is installed with Matplotlib).

## Run

```bash
source .venv/bin/activate
python exp7_result_check.py --self-test
python exp7_result_check.py --smoke --out results/exp7_check_smoke
python exp7_result_check.py --rounds 30 --out results/exp7_result_check
```

The self-test checks the selection and statistical logic, and runs deterministic and input-sensitivity tests using all 29 exact selected configurations. If a required library is missing it stops instead of substituting or skipping it. The smoke test runs one complete round at both worker levels, with no confidence intervals. The real test defaults to 30 independently randomized rounds, 1 and 8 concurrent processes, 1,740 benchmark batches, and at least 0.6 s of work per batch. A more extensive single planned run can use `--rounds 50` (2,900 batches). Do not choose the number of rounds based on an emerging result. Avoid simultaneous benchmarks and heavy background workloads. Keep the same WSL memory/CPU settings. The original experiment used eight workers; change `--workers` only for a separately labeled sensitivity experiment.

## Frozen selection

- Ten best hybrids by screening latency-throughput product, including the exploratory yescrypt and Lyra2 configurations; no filtering by favorable outcomes.
- Ten best standalone configurations by the same product.
- The exact unchanged Argon2 anchors, the three default Argon2 variants, and the screening-selected latency-matched or latency-ceiling controls. Deduplication leaves 19 standalone configurations, 29 total.
- `result_check_selection.json` preserves the exact stage parameters, selection roles, screening rank/measurements, environment and source file SHA-256 checksums. No parameters are changed or retuned during result checking.

## Measurement and analysis

The original Experiment 7 process-pool benchmark is reused, with longer batches and independently generated synthetic fixtures. All configurations and both concurrency levels are randomly ordered inside every round. Each round uses the same synthetic fixture range across configurations; no real accounts, password lists, cracking or GPU measurements are involved. The original median single-derivation latency (seconds) multiplied by median concurrent throughput (derivations/s) is the primary metric: lower is better. It is a performance/scaling metric, not a proof of security. It can reward poor concurrent performance that also affects legitimate servers; latency and throughput, CPU work and sampled worker RSS are retained separately.

Thirty rounds means 30 batch observations at each worker level per configuration, not 30 individual hashes. The program resamples complete rounds together using a fixed-seed paired bootstrap (10,000 resamples). It reports marginal 95% product intervals and approximate simultaneous 95% intervals for the 190 hybrid/control product ratios using the maximum absolute bootstrap log-ratio deviation. These intervals are approximate and rely on the randomized rounds being reasonably representative; thermal drift and temporal dependence can still affect them. A ratio less than 1 favors the hybrid. A candidate is supported as beating every selected standalone only when the simultaneous upper bound is below 1 for every pair. A separate flag requires that bound to be below 0.95 for every pair. A point-estimate winner alone is not confirmation. The selected controls are not every possible Argon2 configuration. No inference is made on a single-round smoke run. The optional yescrypt and Lyra2 backends retain their exploratory status; determinism/input sensitivity are not independent known-answer validation. Argon2d has side-channel concerns. Cipher stages are custom workload constructions, not validated password hashing schemes.

## Output

- `ranking.csv`, `hybrid_ranking.csv`: directly comparable raw products and uncertainty, separate latency and throughput, original screening rank, CPU time and sampled worker RSS.
- `pairwise_comparisons.csv`: all 190 hybrid/control comparisons with simultaneous intervals and flags.
- `raw_batches.csv`: batch-level measurements, flushed after every batch.
- `verified_ranking.png`, `latency_throughput.png`: ranking with marginal uncertainty and latency/throughput scatter.
- `selection.json`, `configs.json`, `environment.json`, `analysis_notes.json`: reproducibility metadata.

If interrupted, the original raw batches are saved. To analyze only complete rounds (clearly report the interrupted run and do not treat this as a planned full confirmation):

```bash
python exp7_result_check.py --analyze-only --out results/exp7_result_check
```

Choose a fresh output folder for a fresh run; the script never overwrites existing measurements. ZIP the complete result directory after completion.

## Validation performed by the assistant

The frozen selection was extracted from the actual supplied screening CSV/JSON. Statistical regression tests passed locally, including a synthetic case where a hybrid beats one control but loses to another. A real selected AES-GCM hybrid and its exact Argon2i anchor completed fixture checks and a small two-worker benchmark, with CSV and graph output. The full 29-configuration run and the native Lyra2 integration were not independently executed here; use your existing WSL setup. No performance results from this confirmation run have been fabricated.
