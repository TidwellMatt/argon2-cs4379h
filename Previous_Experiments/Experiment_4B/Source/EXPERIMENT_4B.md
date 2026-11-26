# Experiment 4B — Input sensitivity of Argon2 time-memory tradeoff estimates

## Purpose
The existing experiment in `experiments.py` tests a single password/salt dependency graph for one-pass, one-lane Argon2d. This extension studies whether that graph is representative. It compares the distribution of the existing model's scores across synthetic passwords and salts, different memory sizes and all three addressing variants. It does not claim to discover a new attack or improve the Argon2 algorithm.

**Research question:** How much do modeled recomputation penalties vary across input values and memory sizes, and does input-dependent addressing introduce measurable variability relative to data-independent addressing?

**Hypothesis (not a result):** For fixed parameters, Argon2i should have identical dependency graphs and model scores when only the password or salt changes. Argon2d and Argon2id can produce different graphs, potentially producing different model scores. The magnitude of the spread is an empirical question.

## Installation and run (Windows PowerShell)
Copy `exp4_extension.py` into the repository root alongside `argon2_impl.py` and `experiments.py`. This is an add-on, not a replacement. From the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe exp4_extension.py --self-test
.\.venv\Scripts\python.exe exp4_extension.py --quick
.\.venv\Scripts\python.exe exp4_extension.py
```

If you already have a working virtual environment, skip creating it. On Linux/macOS use `python3 -m venv .venv` and `.venv/bin/python` in place of the Windows executable. The full run uses 216 hashes of synthetic data and 2,592 model observations by default. `--quick` uses 18 hashes and 108 observations. These are planned counts, not measured results. For an independent repeated run, change the seed and output folder:

```powershell
.\.venv\Scripts\python.exe exp4_extension.py --seed 4380 --output results/exp4b_repeat
```

## Design
- Fix passes and lanes at one each; the original trace model is not valid for multiple passes or lanes without further changes.
- Compare Argon2d, Argon2i and Argon2id at 256, 1,024 and 4,096 blocks (1 KiB per block).
- Vary salt alone (fixed synthetic password), then password alone (fixed synthetic salt), using 12 deterministic samples per condition. All variants receive the same input samples. No real credentials are used.
- Use two fixed retention policies: evenly spaced blocks and a fixed half-uniform/half-frequency hybrid inspired by the original. Do not select the best policy for each input. Both initial blocks count within the exact budget. The hybrid uses whole-graph knowledge, so it is an offline oracle policy, not a demonstrated feasible implementation under the modeled memory limit.
- Use nominal retention fractions 1/2 through 1/7, rounding down to an integer block count; record actual fractions.
- Use the existing experiment's abstract work and depth recurrence; cross-check every row against `experiments.attack_cost` using the same retained set. Count the initial blocks as abstract units, not literal G calls.
- Check every traced output against argon2-cffi. Check trace completeness, earlier references, full-retention scores, exact retained counts, and the data-independent control.

## Outputs
`results/exp4b/` (or `results/exp4b_quick/`):
- `trials.csv`: each model observation, input trial ID, seed, variant, memory size, actual retained fraction, graph fingerprint, reference statistics, C and D.
- `summary.csv`: grouped minimum, median, maximum, sample standard deviation, max/min ratio and distinct graph count for each condition.
- Eight PNG charts: median modeled C or D versus retained fraction, with min–max bands, for each input axis and policy at the largest tested memory size. Smaller sizes remain in the CSV.
- `run.json`: configuration and verification checks.

The min–max bands show observed variation, **not** confidence intervals. The 2,592 observations share graphs across strategies and budgets and are not 2,592 independent trials. Compare rows within the same memory size, policy, and fraction. In the Argon2i control, identical graphs are expected, not independent draws from a varying graph population.

## Interpretation and limitations
The new work is measuring input sensitivity and the representativeness of a single-graph experiment under a fixed model. Merely finding identical Argon2i graphs is a specification-based sanity check, not a novel finding. Any measured spread or lack of spread in the data-dependent variants is the empirical result. Search related literature before claiming novelty; no guarantee of instructor acceptance or worldwide originality is made.

The original uniform policy may exceed its advertised block budget by one because it adds both initial blocks after choosing regular blocks. The extension counts both initial blocks within the budget. It therefore does not exactly reproduce the original storage layout; compare policies within this experiment. No original files or results are overwritten.

Scores C and D are abstract graph-model work and depth estimates, not wall-clock timing, real cracking performance, security proofs, or strict memory bounds. The model omits metadata, temporary blocks, cache reuse, address-generation work and hardware costs. D sums idealized recomputation depths and is not a general latency bound. The fixed hybrid policy uses future reference information. Argon2i/id require extra address-generation operations that this model does not include. Small one-pass configurations are experimental, not deployment recommendations. Do not claim one variant is universally more secure based on these results.

## Verification status
The original GitHub source was inspected in the chat; a direct clone and raw-file download failed in the execution environment. Standalone model self-tests and Python compilation passed. Full integration against the actual repository and the 216-hash experiment must be run locally. No empirical result is supplied with this add-on. Keep the generated CSVs and record the Git commit, Python version and dependency versions in the final report.

## Sources
- Team repo: https://github.com/TidwellMatt/argon2-cs4379h
- RFC 9106: https://www.rfc-editor.org/rfc/rfc9106.html (especially sections 3.2 and 3.4)
- Original paper: https://doi.org/10.1109/EuroSP.2016.31
