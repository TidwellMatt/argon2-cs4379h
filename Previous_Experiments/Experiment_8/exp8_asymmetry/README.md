# Experiment 8 — CPU/GPU Cost Asymmetry Analysis

## Question and scope
Can an Argon2 parameter configuration reduce measured GPU evaluations per second without increasing legitimate CPU latency, relative to a specified same-variant standalone control? This tests an empirical CPU/GPU cost asymmetry, **not** a new cryptographic primitive or a proof of resistance to all attacks. Use only the generated public synthetic fixtures. No real credentials, external hash input or external candidate input are needed or supported by this experiment.

## Windows setup
Use native Windows PowerShell, not WSL, so the same native Windows host is used for both phases. Open PowerShell in the extracted `exp8_asymmetry` directory. Hashcat 8.0.0 and its CUDA 13.5 backend have already completed the user's built-in benchmark; the parameter-specific method below still needs a pilot on that system.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$hc = "$HOME\Downloads\hashcat-8.0.0\hashcat-8.0.0\hashcat.exe"
.\.venv\Scripts\python.exe exp8_asymmetry.py --self-test
.\.venv\Scripts\python.exe exp8_asymmetry.py --hashcat $hc --stage pilot --out results\exp8_pilot
```

If `python` is not found, use `py -3 -m venv .venv` for the first command. If Hashcat is in another directory, edit `$hc`. No execution-policy change or activation is necessary. Keep other CPU/GPU workloads closed, do not change power/cooling profiles mid-test, and prevent sleep. Default GPU temperature abort is 85 C (Hashcat monitoring); CPU thermal monitoring remains manual. Do not use `--force` or disable self-tests.

## Stages

- Pilot: 23 configurations, 2 rounds by default. Covers all variants at 64 MiB, memory/iteration alternatives, both RFC 9106 recommendations, previous GPU reference, previous tuned anchors, and best standalone configuration per variant from Experiment 7's 500-round result checking. The first GPU run is the previously benchmarked reference (Argon2id 64 MiB, t3, p1). The first reference failure stops the pilot for diagnosis. Other failures are retained in the CSV, never ranked as zero throughput. Upload the pilot output directory as a ZIP before expanding.
- Screen: 436 configurations, including 432 factorial combinations (3 variants × 6 memory sizes 16–512 MiB × 6 time costs × 4 lane counts) plus three off-grid anchors and the high-memory RFC control. Use after pilot validation.
- Full: 579 configurations (576 factorial combinations with memory 16–2048 MiB, plus 3 off-grid controls). Optional; expensive and very high memory/iteration configurations may not be supported or useful. The per-run minimum GPU session duration is not the whole runtime; kernel compilation, autotuning, known-input verification and CPU tests add overhead. Do not start both screen and full unless scientifically necessary.
- Confirmation: freezes up to ten non-control candidates from the selected screening directory plus its successfully measured named controls. Defaults to 12 new rounds, adjustable up to 100. Selection prioritizes same-variant latency/GPU improvements, then Pareto candidates; it does not use confirmation data. All successful named controls are retained.

After reviewing the pilot, use one of these commands (keep `$hc` defined):

```powershell
.\.venv\Scripts\python.exe exp8_asymmetry.py --hashcat $hc --stage screen --out results\exp8_screen
# Optional larger grid instead of screen:
.\.venv\Scripts\python.exe exp8_asymmetry.py --hashcat $hc --stage full --out results\exp8_full
# Independent confirmation using the selected screen:
.\.venv\Scripts\python.exe exp8_asymmetry.py --hashcat $hc --stage confirm --from-results results\exp8_screen --rounds 12 --out results\exp8_confirm
```

Every run saves a frozen manifest. If interrupted, rerun the **same command** with `--resume` to continue missing records. Existing failed/skipped records are retained, not silently retried. A new pilot directory is appropriate after resolving a compatibility issue. `--analyze-only --out results\exp8_pilot` regenerates reports without running Hashcat. CUDA is the default; `--backend opencl` is available for a separately labeled comparison, not a silent fallback. No results from Windows and WSL or different drivers/backends should be pooled without justification.

## Measurement design

- Same variant, memory cost (KiB in PHC), t, lane count, version 19, 16-byte salt and 32-byte tag on CPU and GPU. Each GPU configuration uses an internally generated PHC hash with a public known input; successful evaluation of that input is checked before sustained measurement. GPU workloads use a fixed file of one million generated, disjoint synthetic inputs, with no recovered target expected. Input lengths match the CPU's public synthetic input. CPU uses deterministic varying salts; GPU uses one fixed synthetic salt per configuration. Neither measurement estimates cracking success probability or password entropy.
- CPU first, GPU second. Within each phase, independently seeded randomized configuration order per round (except first GPU pilot reference). CPU single-request latency and process CPU time are medians of three native argon2-cffi encoded KDF calls; this is a KDF latency proxy, not network or application login latency. Four simultaneous CPU request workers by default, two waves per round; throughput includes submission and scheduling overhead. Concurrent p95 is service duration after each worker starts, not full server queue latency. Whole-process RSS peak is sampled every 5 ms and may miss short allocations. Conservative available-RAM guard limits concurrent nominal Argon2 memory to 60% of currently available host RAM. High-memory configurations can be skipped.
- Hashcat's built-in `-b` is **not** used to measure custom parameters. Mode 34000 is invoked separately for each internally generated fixture. The fixed synthetic workload is run with a time limit (18 seconds default). For one RTX 4090, the parser takes positive running-status speed readings, discards the first, requires at least two retained readings and an expected end state, and records their median as the round's GPU H/s. Each new process is a separate run. The reported speeds are Hashcat's own throughput estimates; samples within a run are not independent replicates. GPU temperature/utilization from Hashcat and optional device-wide VRAM snapshots from nvidia-smi are recorded. VRAM is total device usage, not exact per-hash allocation; missing telemetry remains blank. Timeouts and errors remain separate statuses. An unavailable configuration is not a security win.
- Keep the backend, driver, host, and workload fixed; collect repeated rounds. CUDA vs OpenCL can be a separate sensitivity analysis. This does not guarantee the fastest possible GPU implementation or represent all attackers (ASICs, other GPUs, distributed systems, time-memory tradeoffs).

## Outcomes and analysis

1. Primary practical comparison: CPU latency and GPU throughput separately. A point-estimate improvement means latency no greater and GPU H/s lower than a named same-variant control. More memory, CPU time, server congestion, or higher concurrent service p95 can make this a resource tradeoff instead of a strict win.
2. `no_defender_resource_regression` applies stricter point-estimate conditions: latency, CPU time, configured memory, sampled RSS and concurrent p95 do not increase; concurrent CPU throughput does not decrease; GPU H/s falls. It is conservative and not a significance test.
3. Secondary descriptive metric: CPU latency in seconds × GPU H/s (lower is better). This product alone does not establish a win, because a candidate can have a better product while raising defender latency or reducing other resources. Do not compare the magnitude directly to the old CPU-only Experiment 7 score.
4. `latency_budgets.csv` identifies the lowest measured GPU H/s for each variant within predeclared CPU latency ceilings (50–1000 ms). `pareto_same_variant.csv` gives the latency/GPU throughput frontiers. Argon2id is the primary password-hashing variant; d and i are separately analyzed because their side-channel and tradeoff properties differ. Do not treat an Argon2d speed result as proof of better password security.
5. Independent confirmation intervals: unadjusted percentile bootstrap (4,000 resamples of round medians, independent CPU/GPU phases) for candidate/control latency and GPU ratios, only if >=5 rounds. A serious claim should predeclare one primary candidate/control pair and a practically meaningful margin, e.g. GPU ratio <0.95 and CPU ratio <=1.0; check both upper bounds plus resources. The provided intervals are exploratory and not familywise-adjusted; avoid declaring a winner by cherry-picking many tests. Repeated benchmarks on one computer are not independent samples of hardware. Temperature, clocks, OS and allocation/tuning effects can cause correlation and systematic error.

## Output
- `manifest.json`, `environment.json`, `hashcat_info.txt`: configuration and environment provenance.
- `cpu_raw.csv`, `gpu_raw.csv`: one row per config/round/phase; failures/skips explicitly marked.
- `gpu_logs/`: full known-input and benchmark logs.
- `synthetic_inputs/`: generated public fixture PHC strings, verification markers, and fixed workload. Can omit the large `workload.txt` from a submission copy; the script deterministically regenerates it.
- `ranking.csv`: only configurations with every requested CPU and GPU round successful.
- `control_comparisons.csv`: named same-variant control comparisons, resource tradeoffs, exploratory CIs when enough rounds exist.
- `latency_budgets.csv`, `pareto_same_variant.csv`, `cpu_gpu_pareto.png`: useful analysis views.
- `confirmation_selection.json`: frozen candidate selection, `analysis_notes.json`: coverage and errors.

## Source references
- RFC 9106, especially sections 4 and 7: https://www.rfc-editor.org/rfc/rfc9106.html
- Hashcat 8.0.0 Argon2 module, including format and published known-answer example: https://github.com/hashcat/hashcat/blob/v8.0.0/src/modules/module_34000.c
- Hashcat 8.0.0 JSON status code and fields: https://github.com/hashcat/hashcat/blob/v8.0.0/src/terminal.c and https://github.com/hashcat/hashcat/blob/v8.0.0/include/types.h
- Hashcat help: https://github.com/hashcat/hashcat/blob/v8.0.0/src/usage.c
