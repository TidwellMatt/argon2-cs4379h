# Experiment 8 — focused 20-round confirmation

Extract this folder inside the existing `exp8_asymmetry` folder. Retain your original Python script and environment. Run in PowerShell from `exp8_asymmetry`:

```powershell
$hc = "$HOME\Downloads\hashcat-8.0.0\hashcat-8.0.0\hashcat.exe"
.\.venv\Scripts\python.exe exp8_asymmetry.py --hashcat $hc --stage confirm --from-results exp8_confirmation_20 --rounds 20 --out results\exp8_confirm_20
```

If interrupted, repeat the same command with `--resume` added. The original script requires this flag and identical manifest settings. It skips recorded attempts including failures; report any failed records and do not interpret them as a security advantage. Keep the same CUDA backend, driver, and settings. Save open work and do not run GPU/CPU-heavy apps concurrently.

After a successful run, optionally execute:

```powershell
.\.venv\Scripts\python.exe exp8_confirmation_20\check_confirmation.py results\exp8_confirm_20
```

ZIP `results\exp8_confirm_20` for analysis. The original benchmark already writes raw CSVs, medians, bootstrap intervals, and plots. The supplemental script checks 20 complete rounds, computes within-round ratios and exact one-sided sign tests; the joint test requires evidence of improvements in BOTH latency and GPU throughput. The primary is 32 MiB/t6/p4 vs RFC low-memory 64 MiB/t3/p4; eight other RFC-low candidates and one p1 candidate vs the single-lane reference are secondary (Holm correction across the nine secondary joint tests). This is a separate secondary family, not a single family-wise claim across primary and secondary. Sign tests assume independent round pairs; thermal or temporal drift could violate that assumption. Resource metrics are descriptive and do not establish non-inferiority. The original bootstrap intervals are unadjusted and exploratory. Neither tool establishes security against alternative implementations or time-memory tradeoffs. All inputs remain synthetic.

Selection uses the uploaded full-screen results: nine Argon2id latency/GPU point-estimate wins against RFC low-memory, five Argon2id controls, and a further strict resource point-estimate win against the single-lane reference. No new selection based on confirmation data. Total: 15 configurations × 20 rounds × 2 hardware phases = 600 measurement records, including 300 GPU runs. Measured full-screen elapsed GPU times imply approximately 100 minutes for the GPU throughput runs alone, plus verification, CPU tests, and overhead. Estimate 1h45–2h15, not a guarantee.

AI audit: the assistant derived the fixed selection from exp8_full.zip's control_comparisons.csv and manifest.json, recorded SHA-256 of both, and wrote this supplemental analysis. The original GPU/CPU benchmark is unchanged. Selection and offline analysis were checked locally; actual confirmation runs must be performed on the user's machine. No claim of a successful result is made in advance.
