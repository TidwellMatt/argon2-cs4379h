# Submission cleanup notes

This is a source-and-data copy of the supplied Argon2_Optimization.zip. Existing experiment code, configuration files, original results, logs, plots and documentation were retained byte-for-byte, except duplicate result ZIPs removed after verification. No research measurements were generated or changed. The supplied folder structure was preserved.

## Removed generated or redundant material

| Category | Files | Uncompressed bytes |
|---|---:|---:|
| Python environments and bytecode | 14,888 | 365,738,350 |
| PyInstaller temporary build files | 9 | 62,501,532 |
| Compiled executable / distribution output | 1 | 58,295,583 |
| Rebuildable bundled Hashcat binary archive | 1 | 46,275,099 |
| Duplicate result archives (SHA-256 verified) | 14 | 23,436,299 |
| Compiled native libraries | 2 | 71,184 |
| Nested upstream Git metadata | 56 | 17,036,320 |

Original files: 18,786. Original files retained (including relocated build-verification records): 3,815. Removed: 14,971.

## What remains

- Final optimizer source folder retains the v4.4 GPU fix README, source files, tests, bundled measured profile, build scripts and audit. Its folder name still contains v4_1; this was not renamed or used to infer an exact build version.
- Original packaged self-test and release provenance are under `release_verification/`; upstream Hashcat license notices and bundle provenance are under `third_party_notices/Hashcat/`. The executable and rebuildable engine archive are excluded. Keep the original executable separately for a release; verify its hash against the preserved provenance.
- Experiment 5B, 5C, 5E (including 5D scripts/docs), 6, 7 and 8 source and result directories are preserved. All five optimizer-mode runs in Previous Results are retained. Development smoke tests remain labeled by their original folder names; do not treat these as full research runs.
- The supplied archive does not include separately named Experiment 4B, 5, 5D results, or 5F directories, nor the later laptop CPU and partial GPU profile results. Add original files separately if desired.
- The optional Lyra2/Catena native source snapshots and revision identifiers are retained; see NATIVE_SOURCE_SNAPSHOT.md for rebuilding without nested Git metadata.
- All removed result ZIPs have byte-identical extracted counterparts, checked using SHA-256.

## Before committing

- Copy the contents into the intended Git branch without replacing teammates’ files. Merge the suggested .gitignore with the existing repository ignore rules.
- Consolidate AI audit entries into the team-level AI_AUDIT.md without deleting other contributions.
- The GitHub Actions workflow is inside the optimizer directory. If you intend to enable it, place it under the repository-root .github/workflows and adjust its working-directory and artifact paths for the final layout. It is not enabled by this cleanup.
- Review logs and metadata for personal paths/identifiers before public publication; originals were not sanitized. A limited scan found path-like strings in 2131 retained results files. No guarantee is made that all sensitive content has been identified.
- Build and runtime tests were not executed as part of this archive cleanup.

## Duplicate result archives removed

- `Previous experiments/Argon2_Experiment_5B/exp5b_extended/results/exp5b_confirm.zip` — 28 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_5B/exp5b_extended/results/exp5b_quick/argon2d.zip` — 30 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_5B/exp5b_extended/results/exp5b_screen.zip` — 31 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_5C/exp5c_global/results/exp5c_screen.zip` — 10 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_5E/exp5e_latency/results/exp5e_screen.zip` — 12 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_6_GPU/exp6_gpu/results/gpu_baseline.zip` — 7 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_7/exp7_stacking/results/exp7_check_smoke.zip` — 10 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_7/exp7_stacking/results/exp7_confirm.zip` — 9 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_7/exp7_stacking/results/exp7_full.zip` — 9 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_7/exp7_stacking/results/exp7_result_check_500.zip` — 10 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_7/exp7_stacking/results/exp7_smoke.zip` — 9 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_8/exp8_asymmetry/results/exp8_confirm_20.zip` — 359 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_8/exp8_asymmetry/results/exp8_full.zip` — 2909 identical files retained in extracted folder.
- `Previous experiments/Argon2_Experiment_8/exp8_asymmetry/results/exp8_pilot.zip` — 129 identical files retained in extracted folder.
