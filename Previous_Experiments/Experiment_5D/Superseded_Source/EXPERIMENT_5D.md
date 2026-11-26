# Experiment 5D: balanced parallelism and resource comparisons

## Question
Does a hybrid derivation reduce concurrent CPU throughput compared with the best tested standalone Argon2, at comparable single-job latency and without increasing defender resource costs? This is a performance study, not a proof of cryptographic strength or an attack against real credentials.

## Inputs and controls
`source_5c_configs.json` is copied from the team's uploaded 5C screening output (`exp5c_screen/configs.json`). It includes 48 standalone controls and 186 hybrids. All original 186 hybrid templates are tested at Argon2 lane counts 1, 2 and 4, totaling 606 configurations (570 with `--skip-bcrypt`). Each Argon2 stage in a given cascade uses the same lane count; independent per-stage lane combinations are not explored. Parameters are retuned to the measured common Argon2id baseline, using a bounded search, not an exhaustive optimum. Paired forward/reverse cascades share stage parameters when their source unordered stages match. For hybrids, tuning adjusts the non-Argon2 stage first and may then adjust both stages. The names retain the 5C template labels for traceability; **use configs.json for the actual tuned memory, passes, iterations and other parameters**, not the descriptive source names. Fixed-memory standalone controls remain fixed. All timings use synthetic fixtures.

## Windows commands
Open PowerShell in this extracted folder.

```powershell
python -m pip install -r requirements.txt
python exp5d_balanced.py --self-test
python exp5d_balanced.py --smoke --out results/exp5d_smoke
python exp5d_balanced.py --screen --out results/exp5d_screen
```

Screening uses 1, 4, 8 concurrent jobs (three repetitions, two jobs per worker per batch). It is substantially larger than 5C. For a shorter screen use `--max-workers 4`; for higher screening concurrency use `--max-workers 12` or `24`. The RAM check uses a conservative estimate; close memory-intensive apps. The output directory must be empty; use a new directory when rerunning. Raw batches and calibration data are written periodically; an interrupted run is not a completed experiment and is not resumable automatically. Do not run GPU and CPU benchmarks simultaneously.

Confirm the best six latency-matched hybrid candidates (even if none pass), retaining the standalone controls and adding direct standalone controls with the actual stage memory and lanes:

```powershell
python exp5d_balanced.py --confirm-from results/exp5d_screen --max-workers 24 --out results/exp5d_confirm
```

Confirmation uses 1,2,4,8,12,16,24 concurrent workers, seven repetitions and three jobs per worker. Use `--top 3` to limit selected hybrids or `--max-workers 8` if RAM is limited. Confirmation does not retune the screened candidates, and matching is reevaluated from fresh measurements. Some configurations may fail latency matching. All comparisons are limited to tested controls; no guarantee of global optimum.

## Reading outputs
- `configs.json`: actual stage parameters.
- `calibration.csv`: pre-benchmark calibration (screening only). `summary.csv` and `ranking.csv` use independent single-worker timings for matching.
- `raw_batches.csv`: per-repetition throughput, task latency, aggregate process CPU time per job, and sampled peak RSS.
- `summary.csv`: all concurrency levels. `ranking.csv`: highest concurrency level. `environment.json`: experimental settings. PNG charts are latency-matched performance summaries, not a proof of security.
- `candidate`: all three variants have matched controls, both common and direct latency comparisons within ±5%, at least 5% lower throughput than lowest-throughput matched standalone across all variants, and lower relative scaling. This is a screening signal only.
- `candidate_with_resource_budget`: also uses no more than 10% additional single-job CPU time and nominal peak stage memory, and no more than 10% + 2 MiB additional sampled RSS increase, relative to that global control. This is a practical resource envelope, not an equality constraint.
- `resource_candidate`: separately compares to lowest-throughput directly latency-matched standalone whose solo resources are not exceeded by the hybrid beyond the same tolerance; requires eligible controls in every variant. This can differ from the unrestricted global comparison. Never report it as beating the unrestricted global winner.
- `best_same_p_control`: separate comparator with matching Argon2 lane count. `passes_at_multiple_high_concurrency_levels` and `paired_repeats_lower` aid confirmation; they do not provide a statistical significance test. Assess run-to-run spread and report null results.

Process CPU time includes all native threads, unlike wall time. RSS is sampled and includes interpreter/allocator overhead; transient allocations can be missed. Nominal stage memory is the maximum of configured stage allocations, not their sum or a measured attacker minimum. Low CPU throughput can reflect CPU contention and can harm legitimate concurrent logins too. An optimized adversary may schedule lanes differently than the reference library, so this cannot establish GPU or ASIC resistance. Argon2d-containing cascades and experimental cipher workloads are not production recommendations. The latter repeatedly encrypt synthetic data and hash outputs; they are not established password KDFs. Do not infer security from adding primitives.

## Optional actual GPU baseline (separate experiment)
Hashcat 7+ includes a standard Argon2 GPU backend, documented in the release notes: https://github.com/hashcat/hashcat/blob/master/docs/releases_notes_v7.0.0.md . Download the official Windows release from https://hashcat.net/hashcat/ and extract it. No password lists, real hashes, or recovery modes are needed. In the 5D directory, run the wrapper with the actual executable location:

```powershell
python gpu_baseline.py --hashcat "C:\path\to\hashcat.exe" --out results/gpu_baseline
```

The wrapper invokes only device discovery, version and the built-in synthetic Argon2 benchmark (mode 34000, GPU device type). It logs raw device and benchmark output and, if `nvidia-smi` is accessible, samples whole-device utilization, memory and temperature. Check that the result identifies the NVIDIA GPU and records the benchmark's variant and parameters before quoting any speed. The built-in parameters are tool-controlled, not automatically identical to 5D. Device telemetry is not process-specific. A driver/runtime problem may prevent running; there is no CPU fallback reported as GPU. **This measures standard Argon2 only. No hybrid has a validated GPU implementation in this package. Do not add separate primitive rates together and present them as a measured cascade.** GPU testing could later be expanded with verified GPU kernels for the full custom cascade, beyond the scope of this package.

## Validation status
Local: syntax; 5C self-tests excluding bcrypt (dependency unavailable); nine Argon2 variant/lane comparisons to high-level reference; coverage and synthetic ranking regression; small 15-config, 30-batch smoke run completed and generated CSVs/charts. Full 606-config run, Windows execution, bcrypt, actual GPU backend and confirmation not verified here. No GPU device/tool is installed in this environment. Novelty in wider literature has not been established. Preserve actual measured data and disclose limitations.
