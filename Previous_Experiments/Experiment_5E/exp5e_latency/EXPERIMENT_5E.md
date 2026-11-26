# Experiment 5E — one-sided authentication latency ceiling

## Research question
Can a hybrid derivation reduce concurrent synthetic CPU derivation throughput relative to the best tested standalone Argon2 while satisfying an authentication latency ceiling and a defender resource budget? This measures native-library performance, not cryptographic security or actual GPU attack performance.

## What changed from fixed 5D
- Keep all 5D method families and lane counts (1, 2, 4). Use the fixed 5D worker, including the Windows zero-CPU-timer fix.
- The primary latency eligibility rule is measured single-worker median latency <= 1.10 times the measured Argon2id baseline median latency. There is no lower bound and no requirement to be within 10% of the chosen competitor. The baseline itself is retained unmodified. Calibration is separate from benchmark eligibility.
- Calibrate hybrids and tunable standalone controls to 50%, 75%, 90%, 100%, and 110% of the common baseline calibration time. Fixed baseline and fixed-memory controls are measured once. The full sweep plans 2,982 calibrations (2,802 without bcrypt); identical calibrated stages are deduplicated and mapped in calibration.csv. Calibration is bounded and may miss its target. The source configurations and memory/pass/lane coverage are inherited from 5D; not a search over every possible parameter setting. Paired forward/reverse cascades share parameters for a given unordered source pair and target.
- The primary comparator at each concurrency is the lowest-throughput standalone from ANY variant or latency target within the same ceiling. Require eligible controls from all three variants before declaring a candidate.
- Maintain the prior 5% minimum throughput reduction and lower scaling ratio criteria. The strict candidate must also stay within 10% of the selected global control's measured solo CPU work and nominal peak stage memory, and within 10% + 2 MiB of its sampled solo RSS increase. Invalid CPU timing fails the resource gate. These are relative comparison budgets, not a guarantee of safe server capacity.
- Keep a separate secondary equal-latency analysis: both candidate and standalone control must be within +/-5% of the common baseline, and the candidate must be within +/-5% of that specific control. This separate comparison uses the fastest-to-evaluate attack-resistance proxy (lowest throughput) among those directly matched controls, requires coverage of all three variants, and still applies the throughput/scaling criteria. Do not mistake secondary results for primary results.
- Record actual calibrated stage parameters in configs.json, not in the historical template labels. New target suffixes denote the requested target, not actual latency.

## Windows commands
Open PowerShell in the extracted exp5e_latency directory. If dependencies are already installed, skip pip.

```powershell
python -m pip install -r requirements.txt
python exp5e_latency.py --self-test
python exp5e_latency.py --smoke --out results/exp5e_smoke
```

For a shorter screening run (recommended if the deadline is close):

```powershell
python exp5e_latency.py --screen --targets 75,100,110 --max-workers 4 --screen-repeats 1 --out results/exp5e_short
```

This deliberately omits the 50% and 90% targets, uses 1 and 4 workers, and makes only one screening repetition. It is exploratory, not confirmation. It still covers all method families and Argon2 lane settings. The full sweep is considerably larger:

```powershell
python exp5e_latency.py --screen --out results/exp5e_screen
```

Default screening uses 1, 4, and 8 workers, two repetitions per configuration, all five target percentages. Use `--targets` for other subsets. The output directory must be new or empty. A full sweep may be time-consuming; do not run the GPU benchmark at the same time. Calibration and raw batches are saved periodically, but interrupted experiments are not automatically resumable and are not complete results.

Confirmation retains all standalone controls and selects up to six hybrids under the latency ceiling, ranking strict candidates first. It adds direct standalone controls at finalist stage memory and lane settings and measures everything afresh. No finalist retuning. Default seven repetitions. Change `--max-workers` if RAM is constrained. Use the folder you actually screened:

```powershell
python exp5e_latency.py --confirm-from results/exp5e_short --max-workers 8 --out results/exp5e_confirm
```

For the full screening folder, substitute `results/exp5e_screen`. If desired, use `--max-workers 24` on a sufficiently resourced machine. The script enforces the same numerical eligibility criteria during confirmation as screening. `--tolerance 15` permits up to 15% extra authentication latency; default remains 10%. `--equal-tolerance 5` is independent and defaults to 5. `--resource-tolerance 10` and `--min-gain 5` remain unchanged. Confirm with matching flag values if you change them at screening. Use `--skip-bcrypt` only if bcrypt is unavailable; that deliberately removes the bcrypt family.

## Results
- `ranking.csv`: largest tested concurrency, primary one-sided comparisons. `within_latency_ceiling` (also legacy alias `matched`), `candidate`, `candidate_with_resource_budget`, `best_global_standalone`, `throughput_vs_best_pct` are the key fields.
- `equal_latency_ranking.csv`: secondary subset close to the original anchor, with `equal_latency_candidate` and `best_equal_latency_control` fields. Fast configurations outside the symmetric band still participate in the main ranking.
- `summary.csv`: all worker levels, resource-matched and same-lane comparisons, repeat ranges and repeat wins. `resource_candidate` is a separate comparator subset, not equivalent to beating the unrestricted global control. `passes_at_multiple_high_concurrency_levels` requires the strict candidate flag at every measured level >=4, with at least two such levels. Neither is a significance test.
- `calibration.csv`: requested target, calibration estimate, and `benchmarked_as` for deduplicated configurations. `configs.json` stores actual stage specifications. `raw_batches.csv` stores individual batch data. `environment.json` contains settings and measured anchor/ceiling.
- Charts include `latency_throughput.png`: lower-left is desirable for these two metrics, but resource budgets and reproducibility still matter. Charts are descriptive, not evidence of cryptographic strength.

## GPU and limitations
The existing 5D GPU baseline wrapper is included unchanged; it only uses an external standard Argon2 synthetic benchmark. No custom hybrid GPU implementation exists here. See the optional GPU section of `EXPERIMENT_5D.md` (historical reference) for setup. CPU results cannot establish GPU or ASIC resistance, and lower CPU throughput also limits legitimate concurrent authentication. Argon2d has side-channel concerns; experimental encryption cascades are not established password-storage schemes. Faster authentication alone does not prove preserved security. Novelty in published literature remains unverified. No result is guaranteed to favor a hybrid.

## Verification
Local syntax and self-tests passed with bcrypt excluded (not installed locally). The regression tests verify faster hybrid eligibility, inclusion of faster standalone controls, rejection above the ceiling, separation of equal-latency analysis, and safe handling of zero CPU readings. A 33-configuration smoke run completed calibration and 30/66 subprocess benchmark batches before the environment timed out. A separate real five-configuration, ten-batch in-process test completed summary and all five charts. Full Windows smoke, full sweep, confirmation, bcrypt and GPU execution still require local verification. No performance results are supplied as research findings.
