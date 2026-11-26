# Experiment 5B — Expanded hybrid KDF screening

## Research question
At approximately equal single-worker latency, do sequential combinations of password-based key derivation functions exhibit lower concurrent synthetic derivation throughput than standalone Argon2 on the tested CPU? Does the answer depend on the Argon2 variant or the order of the stages?

This is an exploratory performance experiment, not a production password-storage scheme, real password recovery test, or proof of cryptographic security. All inputs are deterministic synthetic fixtures. No password lists, accounts, or GPU/ASIC attack implementations are used. Argon2d and any cascade containing it have data-dependent memory accesses; they are research comparators, not password-storage recommendations.

## Setup (Windows PowerShell)
Extract the ZIP, navigate to the directory containing `exp5b_extended.py`, and run:

```powershell
python -m pip install -r requirements.txt
python exp5b_extended.py --self-test
python exp5b_extended.py --quick --out results/exp5b_quick
python exp5b_extended.py --screen --out results/exp5b_screen
python exp5b_extended.py --confirm-from results/exp5b_screen --out results/exp5b_confirm
```

For a more exhaustive initial run, replace `--screen` with no mode flag. Use a fresh output directory each run. `--quick` uses 16 MiB and 1–2 workers; `--screen` uses the full-size default of 64 MiB, 3 baseline passes, 1–4 workers and two repetitions. The default full run uses five repetitions; confirmation uses seven and reuses the selected screening configurations exactly, with fresh synthetic input offsets and a different batch-order seed. Confirmation selects the three lowest-throughput matched hybrids per variant (even if none beat the control) plus all standalone controls. Do not use quick results as confirmation inputs if you intend to evaluate the 64 MiB configurations. The optional `--variant argon2id`, `--variant argon2i` or `--variant argon2d` restricts a run to one variant. Default is `all`. `--max-workers 8` is available for screen/full runs; ensure adequate RAM. `--memory-mib`, `--max-memory-mib`, `--passes`, and `--tolerance` change experimental conditions; record them. `--skip-bcrypt` disables optional bcrypt-PBKDF if unavailable. Without bcrypt installed the program explicitly reports skipping it. These settings are research settings, not recommended production settings.

## Design
Each of the three Argon2 variants (version 19, one lane, 32-byte tags) has a separate 64 MiB, three-pass baseline by default. The script also tunes standalone variants with fewer passes and larger memory, within a configurable memory cap (default 3x baseline memory). Hybrid families include PBKDF2-HMAC-SHA256, SHA512, SHA3-256, scrypt, optional bcrypt-PBKDF (not standard bcrypt password hashing), repeated same-variant Argon2 and mixed-variant Argon2. Most cascades use both orders with identical stage parameters. Every stage uses a domain-separated salt derived from the fixture salt; the previous stage's 32-byte output becomes the next stage's input. Timing is calibrated empirically and independently remeasured during benchmarking. No actual reversible encryption is evaluated.

Configurations are benchmarked on a randomized batch order, with each batch in a fresh subprocess to reduce cross-configuration allocator effects. Each batch measures synthetic derivations per second, median task duration, process CPU time per job, and sampled peak resident memory. Memory sampling can miss short-lived peaks. Library versions and environment are recorded. Calibration is not exact; the default final latency-match tolerance is ±5% relative to that variant's baseline. Unmatched configurations are excluded from primary comparisons. A candidate must also beat the slowest-throughput matched standalone control, not merely the original baseline. A negative percentage is lower measured throughput, not proven increased security. A small difference or one selected from many candidates may reflect noise; independently confirm and examine ranges/repetitions before interpreting it. Cross-variant comparisons need care because each has its own latency target; a common-latency cross-variant ranking is not provided.

## Output
Each variant subfolder includes configs.json, calibration.csv (screening only), raw_batches.csv, summary.csv, ranking.csv, environment.json, throughput.png, latency.png, memory.png, scaling.png. The top folder includes all_variants_ranking.csv. Look at `matched`, `throughput_change_pct`, `change_vs_best_standalone_pct`, `candidate_improvement`, `relative_scaling`, and `throughput_min` / `throughput_max`. Candidate flag is a screening heuristic only; it is not a statistical significance test. Do not choose the final conclusion in advance. A lower concurrent derivation rate could also mean reduced throughput for a legitimate server; it is not an asymmetric cryptographic advantage by itself. GPU/ASIC performance, side channels, actual password recovery, and novel cryptographic security properties are not established by this test. Wider literature novelty remains unverified.

## Verification completed by AI assistant
Syntax compilation and self-test passed (PBKDF2 SHA256/SHA512 and scrypt known answers; all three Argon2 variants checked against high-level argon2-cffi; deterministic cascades/input sensitivity). Small in-process benchmark, summary and four-chart tests passed for every variant. An earlier Argon2id-only minimal pilot completed; the expanded all-variant subprocess smoke run was interrupted by the execution limit after reaching 40/48 batches of the first variant. No complete all-variant performance data are claimed. Optional bcrypt-PBKDF was unavailable in the test environment and was not executed. Run locally and review failures, calibrations and results. The program is independent of earlier experiments.
