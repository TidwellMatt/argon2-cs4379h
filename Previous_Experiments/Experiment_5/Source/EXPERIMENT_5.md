# Experiment 5 — Hybrid password hashing under an equal latency budget

## Research question
For approximately the same single-request latency and nominal Argon2 memory allocation, does redistributing work from Argon2id passes to a second key-derivation function change concurrent derivation throughput, CPU time, or peak process memory?

**Hypothesis:** Cascades can exhibit different scaling under concurrent workloads because they allocate work differently between compute and memory. The direction of the effect is unknown. This is a performance experiment, not a demonstration of increased cryptographic security. A negative result is meaningful. Novelty in the literature has not been established.

## Configurations
- Baseline: Argon2id, t=3, p=1, m=64 MiB (full mode).
- PBKDF2-HMAC-SHA256 then Argon2id, and reversed, with t=2 or t=1. Within each forward/reverse pair the iteration count is identical.
- scrypt then Argon2id, and reversed, with identical parameters within the pair. scrypt uses r=8 and calibrated N and p; nominal scrypt working memory 128*N*r bytes is constrained to the Argon2 allocation. This does not guarantee equal actual process RSS.
- Every stage outputs 32 bytes. A cascade passes the raw output of its first stage into the second. Each stage receives a distinct 16-byte salt derived from a public synthetic master salt, order and primitive label. These are lab fixtures, not production password records.
- The baseline also uses the native argon2-cffi implementation so no comparison is confounded by the teammate's pure-Python implementation. This script is independent of Experiments 1–4B.

## Run from your repository (Windows PowerShell)
Copy `exp5_hybrid.py`, this document and the audit notes into your repository. Install in your existing venv:

```powershell
python -m pip install argon2-cffi psutil matplotlib
python exp5_hybrid.py --self-test
python exp5_hybrid.py --quick --out results/exp5_quick
python exp5_hybrid.py --out results/exp5
```

Optional second full run on the same or another machine: `python exp5_hybrid.py --memory-mib 32 --out results/exp5_32mib`. Use a separate output folder for each run; files in the same output folder are overwritten. Full mode uses 1, 2, 4 worker threads, 5 repetitions and 6 tasks per worker per batch (105 batches, 1470 timed derivations, excluding calibration and tests). Quick mode uses 16 MiB, 1 and 2 threads, 2 repetitions, 3 tasks per worker (28 batches, 126 timed derivations). Run with enough free memory (default full mode can allocate at least 256 MiB for four simultaneous Argon2 instances plus runtime and scrypt overhead). Avoid other heavy workloads. This is a local synthetic experiment, not a tool for real account or password cracking.

## Methodology
1. Warm each calibration candidate and estimate baseline median latency. Tune PBKDF2 iterations and search a discrete scrypt grid with fewer Argon2 passes. Reverse-order pairs use identical settings. Target approximate latency, not exactly equal security or time-memory cost.
2. Verify primitive known answers (PBKDF2 and scrypt), baseline Argon2 against the high-level API from the same library, deterministic tags, changed input and changed salt. These are sanity checks, not an independent cryptographic proof.
3. Randomize batch order using seed 4379. Use fresh subprocesses per batch to isolate process RSS. Each task derives one synthetic value with a fixed distinct fixture. The same input fixtures are used across schemes. No leaked credentials or recovered passwords.
4. Measure batch wall time, per-task service time (excluding queue wait), process CPU time per derivation, throughput and sampled peak process RSS (approximately every 2 ms). RSS includes interpreter, libraries and allocations and may miss short peaks. It is not exact KDF working memory or memory-time product. The batch process starts cold; calibration is warmed, which can contribute to timing differences.
5. Compare the median single-worker service time measured in the separate batches to the measured baseline. Flag configurations outside ±15%. Do not use unmatched rows to claim a fair comparison; rerun in a quiet environment if necessary. Tolerance is an experimental choice, not a standard. The full mode has more repetitions. Reverse-order comparisons require both configurations to be matched, and parameters are identical for each pair.
6. Compare concurrent throughput for matched rows only, alongside CPU time and measured memory; report min/max throughput across repeats, hardware and software. Repeat on a teammate's machine for robustness. No GPU, ASIC, offline-cracking, password-recovery, or security proof is included. A local CPU throughput difference alone does not establish a change in resistance to an optimized adversary.

## Outputs
- `configs.csv`: chosen parameters (m in KiB; sp is scrypt p; r=8).
- `calibration.csv`: initial target and candidate latency.
- `raw_batches.csv`: one row per timed batch.
- `summary.csv`: median batch metrics, throughput range, independent single-worker mismatch and match flag.
- `calibration.png`, `throughput.png`, `memory.png`, `latency.png`: plots; asterisks flag unmatched schemes on line plots.
- `environment.json`: platform, library versions, test results and run settings.

## Included example_results (pilot only)
The included quick run completed all 28 batches and passed the self-tests. However, its independently measured baseline median was 28.56 ms and all six cascades were outside the ±15% window (37.35–54.50 ms). Consequently **none of these pilot comparisons support an equal-latency conclusion**. The results are provided transparently to demonstrate that the pipeline and mismatch flag work; rerun on local hardware before using results in the paper. An earlier exploratory run also passed the checks but had different calibration settings and is not included. Do not substitute either pilot for a full local experiment. No results have been manufactured.

## Possible paper contribution
A controlled empirical evaluation of how reallocating a fixed single-request latency budget across a memory-hard and/or compute-intensive KDF affects concurrent resource usage. Do not claim a new KDF, new provably secure construction, improved attack resistance, or first-ever cascade without evidence. If calibration succeeds but results are inconclusive, report that. If calibration fails, report that as a limitation and adjust methodology transparently rather than cherry-picking data.

## References to verify
- RFC 9106 (Argon2): https://www.rfc-editor.org/rfc/rfc9106.html — parameter selection and memory hardness.
- RFC 7914 (scrypt): https://www.rfc-editor.org/rfc/rfc7914.html — specification and test vectors.
- RFC 8018 (PBKDF2): https://www.rfc-editor.org/rfc/rfc8018.html
- argon2-cffi API: https://argon2-cffi.readthedocs.io/en/stable/api.html
- OWASP Password Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html — established password-hashing guidance. Experimental cascades are not recommended as replacements for standard schemes.
