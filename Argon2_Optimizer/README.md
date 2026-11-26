# Empirical Hardware-Aware Argon2id Parameter Optimizer

Research prototype · CS4379H · v2.0

The optimizer measures the **defender CPU locally** and looks up measured GPU guessing rates in an offline, reusable profile. It supports five optimization objectives; the original maximum-defense mode searches for the lowest maximum observed GPU throughput among configurations that pass user-defined authentication/resource constraints. It uses only Argon2id for recommendations and public synthetic inputs for local testing. It does not require a GPU, CUDA, Hashcat, internet access after installation, or passwords.

## Quick start (Windows)

1. Extract this ZIP to a new directory. Do not put it inside Experiment 8 or overwrite that experiment.
2. Double-click `setup_windows.bat` once. This creates a virtual environment and installs two Python dependencies. Python must already be installed (3.10–3.13 recommended; local test used Python 3.11).
3. Double-click `start_optimizer.bat`. Enter the limits when prompted, or press Enter to accept defaults. Extra CPU/resource constraints may be left blank. The program writes a new results folder each run.

PowerShell alternative, from the extracted `argon2_optimizer` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe optimizer.py self-test
.\.venv\Scripts\python.exe wizard.py
```

Linux/macOS: use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, and `.venv/bin/python optimizer.py self-test` / `wizard.py`. Windows launchers have not been executed in this Linux test environment. The CLI does not require GUI installation. See DESKTOP_README.md for the optional desktop edition and Windows EXE build.

## Reproducible CLI

```powershell
.\.venv\Scripts\python.exe optimizer.py optimize --latency-ms 100 --max-memory 256 --workers 4 --out results\demo
```

Optional additional limits: `--max-cpu-ms 200 --max-p95-ms 300 --max-rss-mib 1500 --min-throughput 10`. Use `--max-tests 20` for a bounded demonstration (may return no recommendation); the default has no count cap, stops after the first confirmed feasible candidate. Use `--exhaustive` to test every policy-eligible candidate. Default two screening and five independent confirmation rounds; `--screen-rounds 3 --confirm-rounds 20` for more testing. The reference is measured separately after the search. Use a fresh output directory for each run. This prototype does not resume a live CPU run; completed CPU rows are saved progressively, and an interrupted run can be inspected but must be restarted in a new folder.

Default limits are illustrative, not universal production requirements. `--max-memory` is Argon2 memory per request, not whole-process memory. `--workers` sets simultaneous authentication jobs. The memory guard skips configurations if estimated simultaneous working memory exceeds 60% of currently available RAM. p95 measures task execution time in closed-loop batches, not network/service/queue latency. RSS is sampled process memory, not a hard memory ceiling. Close unnecessary apps and keep power settings fixed while benchmarking.

## Optimization modes (v2.0)

Choose a GUI tab or pass `--mode defense|balanced|responsive|efficient|comprehensive` to `optimize`.

| Mode | Objective (all constraints still apply) |
|---|---|
| defense (default) | Lowest stored maximum GPU H/s; GPU-ordered early stop. |
| balanced | Lowest confirmed median latency in seconds × maximum stored GPU H/s. |
| responsive | Lowest confirmed median login latency; requires `--max-gpu-hps`. |
| efficient | Lowest confirmed median CPU time; ties prefer less Argon2 memory then lower sampled RSS; requires `--max-gpu-hps`. |
| comprehensive | All eligible candidates screened; rank confirmed candidates by defense and report their Pareto frontier. No unique universal winner. |

All modes other than defense screen every eligible configuration, confirming each that passes screening. They may take considerably longer than defense. A GPU ceiling is an empirical target, not a cryptographic guarantee. The GUI defaults to an editable 1000 H/s target in the two target-required modes, an illustrative value rather than a security standard. All local limits and the default Argon2id security policy remain unchanged. A candidate that fails screening or cannot be measured is excluded from the final confirmed ranking. Rankings reflect the observed data, not guaranteed true optima. For all modes the program writes `confirmed_ranking.csv` and `pareto_frontier.csv`; the latter identifies non-dominated confirmed results using GPU H/s, latency, CPU time, required memory, sampled RSS, concurrent p95 and concurrent throughput (higher is better for throughput). In defense mode this frontier only includes the candidate(s) actually confirmed. Comprehensive mode shows the defense-first choice alongside the frontier.

Example: `python optimizer.py optimize --mode balanced --max-memory 128 --latency-ms 100 --out results/balanced`.

## Search method and security policy

1. Require exact parameter matches (Argon2 version 19, 32-byte output, 16-byte salt) in every selected GPU profile; missing data are not treated as zero throughput.
2. Filter Argon2id candidates by memory and pass limits. Default floor: at least 64 MiB and 3 passes, with a specific exception for the RFC 9106 2 GiB, t=1, p=4 recommendation. The floor is a conservative project design rule, not a proof of equivalence to RFC settings for arbitrary parallelism. Raise `--min-memory` or `--min-passes` to make the policy stricter. `--research-relaxed --min-memory 32 --min-passes 3` enables the 32 MiB research candidates; outputs are labeled research-only and should not be treated as deployment recommendations. The minimum relaxed limits are 19 MiB and 2 passes; this is not a general security certification.
3. Rank candidates by the maximum observed per-run GPU H/s across selected profiles; tie-break by the maximum profile median and configuration ID. This is an empirical conservative score, not a confidence bound or future worst-case bound. Profiles with different repetition counts can have different observed extrema; expose round counts rather than treating evidence as equally precise.
4. Measure CPU wall latency and CPU consumption with warm-up and repeated native library calls. Benchmark concurrent throughput, p95 execution latency and sampled RSS in three closed-loop waves. Screen using the maximum observed round metric (minimum for throughput); independently repeat feasible candidates. Require every observed confirmation round's summarized measurements to satisfy the specified limits.
5. In maximum-defense mode, return the first passing candidate in GPU-score order; later candidates cannot have a strictly better stored score, but earlier screening failures may be false negatives. No claim of true global optimality. If none passes, return no recommendation rather than weakening the policy. An optional exhaustive defense mode and the four additional optimization modes screen all eligible candidates. Five or more confirmation rounds produce exploratory median bootstrap intervals, not multiplicity-adjusted significance or future service guarantees.

## Bundled empirical dataset

`profiles/rtx4090.json` contains **579 configurations**, including **193 Argon2id configurations**, from the actual Experiment 8 full sweep (2 repetitions per configuration) and confirmation (20 repetitions for 15 configurations). For overlapping configurations, the 20-run source replaces the 2-run source; they are not pooled. It includes per-round GPU speeds, provenance, software version and source file digests. The importer reconciled all 1,458 original GPU medians with corresponding status logs and checked the matching device and known-input verification records. This is consistency checking, not proof that third-party submissions are authentic. The profile describes one RTX 4090 with Hashcat 8.0.0/CUDA, not every attack implementation.

## Additional GPU profiles

Import a compatible Experiment 8 result directory or ZIP containing `manifest.json`, `environment.json`, `gpu_raw.csv`, verification records and GPU logs:

```powershell
.\.venv\Scripts\python.exe optimizer.py import-profile --source other_results.zip --device "RTX 4080" --id rtx4080_cuda --out profiles\rtx4080.json
.\.venv\Scripts\python.exe optimizer.py optimize --profile profiles\rtx4090.json --profile profiles\rtx4080.json --latency-ms 100 --max-memory 256 --out results\multi_gpu
```

Multiple `--source` inputs can merge compatible runs for the same profile. Only complete, verified configurations are imported. The source format must match Experiment 8 and use a single matching GPU. The original Experiment 8 collector was hard-coded to the RTX 4090. Version 3 added an optional local, single-GPU Argon2id profile collector in the desktop app, with checkpointed pause/resume and explicit Hashcat backend/device selection. See DESKTOP_README.md. Live cross-GPU and Windows validation remain pending; the app does not provide an online submission service. Multiple profiles restrict recommendations to common coverage; a small partial profile can shrink the search space substantially. Use trusted profile files. Cross-GPU validation and community database moderation are future work.

## Research validation

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_optimizer
.\.venv\Scripts\python.exe optimizer.py replay --out results\replay
```

Historical replay uses original screening and confirmation data separately: eight latency budgets × five memory budgets × two datasets = 80 scenarios. This tests the exact GPU-ordered early stopping logic against exhaustive ranking using identical stored latency point estimates. It is an **in-sample algorithm check** and is expected to match the oracle by construction; it does not validate local measurement noise, concurrency limits or performance on other hardware. A simple CPU-only comparator chooses maximum memory then maximum passes among feasible choices; it is illustrative, not a recreation of Cryptsetup or Multifactor. Results in `validation/replay/` show 75 feasible scenarios, 80/80 matching outcomes including infeasible ones, 823 vs 2164 candidate checks across feasible scenarios (62.0% fewer), and lower empirical GPU throughput than the illustrative CPU-only heuristic in 27/75 feasible scenarios. These figures are candidate counts, not measured runtime speedups or security proofs. The historical CPU data are never used to recommend live settings.

## Outputs

- `confirmed_ranking.csv`: all independently confirmed feasible candidates ranked by the chosen objective.
- `pareto_frontier.csv`: non-dominated confirmed candidates.
- `REPORT.md`: readable recommendation and comparison with the RFC low-memory control, if available.
- `recommendation.json`: machine-readable selected parameters, local CPU metrics, profile-specific estimates, exploratory bootstrap intervals and limitations.
- `tested.csv`: candidates attempted, screening and confirmation outcomes, constraint bounds, errors.
- `cpu_rounds.csv`: raw local per-round measurements.
- `run.json`: settings, environment and profile file hashes.

## Limitations and related work

An attacker may use different hardware, optimization, parallelism, time-memory tradeoffs or multi-GPU equipment. GPU throughput is a measured implementation-specific proxy, not total attack cost, security proof, or guarantee. The estimator is not a cryptographic modification. The user must review deployment policies, denial-of-service constraints, salt generation and actual server workload separately. The research aim is to evaluate empirical profile reuse and workload-aware selection, not claim invention of parameter calibration or GPU-aware selection. Related work: RFC 9106 §4 (https://www.rfc-editor.org/rfc/rfc9106.html#section-4), Cryptsetup (https://gitlab.com/cryptsetup/cryptsetup), Multifactor KDF selection (https://multifactor.com/blog/kdf-parameter-selection-part-1). A full novelty review and independent cross-hardware testing remain necessary.

## Desktop v3
The desktop remembers one shared results location for all five modes, includes the mode in each run folder name, defaults to dark mode, and adds optional GPU profile collection. See [DESKTOP_README.md](DESKTOP_README.md). The existing GPU database and CPU selection logic are unchanged.

## Desktop v4 distribution

The desktop release build now packages the official pinned Hashcat 8.0.0 distribution inside the single-file Windows executable and resolves it automatically for profile generation. Ordinary CPU optimization remains GPU-independent. The build script can use the official archive or download it at build time; it preserves upstream license notices, records hashes, and checks the packaged engine version. GPU drivers and backend runtimes are not bundled. Use the Windows BAT or the included GitHub Actions workflow; the resulting EXE, not the source ZIP or BAT, is what teammates run. See DESKTOP_README.md for distribution and verification limits. No Windows binary was produced in the Linux preparation environment.


## v4.1 build fix
The official Hashcat 8.0.0 archive uses BCJ2, which py7zr does not support. The build now tries installed 7-Zip, then the Windows system tar.exe. It checks extraction success and expected release layout before running the version check. If neither works, install current x64 7-Zip from https://www.7-zip.org/ and rerun the BAT. No change to optimizer code or GPU data. Only the builder needs the extractor; recipients still receive the standalone EXE. A fresh official archive is used, not a previously used Hashcat folder. An independently verified upstream digest or signature is still recommended; the download alone is not signature verification.
