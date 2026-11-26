# Experiment 5F — Full-cost cryptographic stacking

Purpose: compare complete Argon2 stages with the same unchanged stage plus another primitive in either order. This is a synthetic CPU throughput experiment, not a password cracker or a production password-storage recommendation. No real password lists, accounts, or hash targets are used. A GPU version of these custom cascades is not implemented.

## Windows quick start

In PowerShell in this folder:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyescrypt
python exp5f_stacking.py --self-test
python exp5f_stacking.py --smoke --out results/exp5f_smoke
python exp5f_stacking.py --screen --out results/exp5f_screen
```

`pyescrypt` is optional; its Windows wheel may not support every installation. Do not confuse it with `pyyescrypt`. A missing library is explicitly logged and skipped. The script does not fabricate data. For a shorter run use `--one-level` (one work level per extra stage), `--max-workers 4`, or `--repeats 1` (exploratory only). `--full-grid` adds all three parallelism settings to the fixed 64 MiB anchors, with the previous tuned anchors retained. No latency ceiling is used. The finite grid is intentional: exhaustive unbounded search is impossible. Standalone controls cover 64/128/192/256 MiB, t=1/3/4/6, p=1/2/4 and the exact strongest tuned configurations from 5E. Default fixed hybrid anchors: each of the three variants at m=64 MiB, t=3, p=1, plus Argon2id(135,4,4), Argon2i(170,3,4), Argon2d(157,3,4). Both orders share identical parameters. No tuning reduces these stages. The added stage has two fixed work levels.

```powershell
python exp5f_stacking.py --confirm-from results/exp5f_screen --max-workers 8 --out results/exp5f_confirm
```

Use the same worker count for primary screening/confirmation comparisons. Seven independent repetitions, top eight non-exploratory hybrids, up to three exploratory hybrids, Pareto controls, top standalone score controls, and all selected anchors. Confirmation is conditional on the tested search space, not a cryptographic proof. Compare the original run and the confirmation independently; do not cherry-pick. `--extra-only` focuses on the four new KDFs plus controls.

## Extra methods

- Balloon SHA256: single-lane, delta=3, 4096 or 32768 blocks, 3 passes. Nettle if available; otherwise a built-in Python reference. The Python implementation is cross-checked against three published known answers. Native is preferred for performance comparisons; Python fallback is exploratory. On Windows set `$env:EXP5F_NETTLE = 'C:\path\to\libnettle-8.dll'` if you have a compatible trusted installation. The actual DLL name can differ.
- yescrypt: optional `pyescrypt` package with N=16384/65536, r=8, p=1, deterministic JSON serialization normalized by SHA256. On Linux, a libxcrypt fallback uses modular crypt cost 3/5 and hex-encodes binary input, normalizing the resulting MCF string by SHA256. Different constructions: do not pool their results. Its memory figure is a conservative guard estimate, not a measured requirement.
- Lyra2: optional reference library exposing the documented `PHS` API. t=1, rows=1024/4096, expected build columns=256, 96-byte blocks, one lane, BLAKE2 sponge. Nominal memory is based on these build settings.
- Catena-Dragonfly: optional reference library exposing `PHS`. t=2, m_cost (garlic)=18/20. Nominal graph storage estimate is not an exact allocation.

Lyra2 and Catena have no bundled Windows binary. They can be built in Linux/WSL with `setup_extra_linux.sh` (untested compilation here). In Ubuntu/WSL, if already installed, navigate to the extracted folder via `/mnt/c/...`. You may need `sudo apt install git gcc python3-venv libnettle8` (package name depends on Ubuntu version). Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
bash setup_extra_linux.sh
python exp5f_stacking.py --self-test
python exp5f_stacking.py --screen --extra-only --out results/exp5f_wsl_extra
```

This optional build script clones public upstream reference code and writes `.so` files locally, but could not be executed in the offline environment. If a build fails, do not substitute a toy implementation or use bogus data. You can also set `EXP5F_LYRA2` / `EXP5F_CATENA` to the absolute path of a compatible trusted DLL/shared library exposing `PHS` with the same parameters and version. For Windows in PowerShell use `$env:EXP5F_LYRA2 = 'C:\path\to\liblyra2.dll'`, similarly for Catena. These must be built from the named reference source and must not be arbitrary DLLs. Do not combine Windows and WSL timing results as if measured in the same environment. Run the same controls in WSL. Yescrypt, Lyra2 and Catena adapters have only deterministic/input-sensitivity checks in this package; independent known-answer validation is still required before making strong claims. No performance result is recorded for unavailable methods.

Sources: https://raw.githubusercontent.com/gnutls/nettle/master/testsuite/balloon-test.c ; https://github.com/0xcb/pyescrypt ; https://github.com/leocalm/Lyra ; https://github.com/medsec/catena . Review source revisions and upstream test vectors, record them in AI_AUDIT.md.

## Ranking

Let L be median single-derivation task time in seconds and G be median concurrent synthetic throughput in derivations/sec, measured at a specified process count. Lower L and lower G are preferred. The primary dimensionless performance score is `(L_default * G_default)/(L * G)`; higher is better. Score 1.0 equals the default Argon2id. Doubling latency and halving throughput gives the same score. It is equivalent to the reciprocal of a concurrency scaling proxy, not a security guarantee. It can favor workloads that fail to scale well for implementation-specific reasons and does not imply an advantage against optimized GPU code. The separate `score_vs_anchor` measures each hybrid relative to its unchanged Argon2 stage, and `score_vs_best_standalone` compares with the best standalone score at that worker count. The actual latency/throughput, Pareto frontier, and CPU work must always be examined as well. `best_control_within_110pct_latency` is the lowest-throughput tested standalone whose measured latency is no more than 110% of the hybrid's latency; `equal_latency_control` is two-sided ±10%. A rough screen flag requires 5% better score and 5% lower throughput than that standalone, and excludes exploratory backends. None of these flags are security certifications. Argon2d-containing constructs have side-channel concerns, regardless of score. Encryption workload stages use the existing 5C cipher+SHA256 construction on a fixed public payload; they are not standard password KDFs.

The experiment uses process concurrency (rather than earlier thread concurrency) to avoid Python GIL artifacts and reduce startup overhead; all configurations use the same persistent pool. The one-task time excludes IPC and startup, concurrent throughput includes dispatch and wave scheduling. Each task uses a deterministic synthetic fixture. CPU time is per worker process, RSS is aggregate sampled child-process memory including idle worker overhead; neither is a definitive algorithm memory measurement. Pool reuse and wave synchronization may influence measurements. A RAM guard is conservative; no algorithm parameters are reduced automatically. Avoid running other benchmarks or games at the same time. This is not directly comparable to prior 5E CPU-throughput numbers due to the changed scheduling backend.

Outputs: `ranking.csv`, `hybrid_ranking.csv`, `pareto.csv`, `summary.csv`, `raw_batches.csv`, `configs.json`, `environment.json`, `score.png`, `latency_throughput.png`. Upload the entire result directory after screening. If interrupted, partial raw CSV is retained, but incomplete batches are not valid for final ranking. Use a fresh output folder on reruns.
