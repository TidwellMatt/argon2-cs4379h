# Recovered Argon2 research files

This archive recovers actual files available in the project conversation on 2026-11-26. It is not a reconstruction of missing raw measurements. Files copied or extracted from previous uploads and generated source archives are byte-for-byte preserved; the recovery notes and manifest are newly created. No benchmarks were rerun or fabricated. The current optimizer source/executable is intentionally not included: use your working patched v4.4 folder for that separately.

## Layout

- `Previous_Experiments/`: historical source packages, original experiment outputs, including negative findings, and documentation. Each Source folder contains that experiment's historical source and audit notes. Preserve these versions for reproducibility; do not mistake them for the final optimizer.
- `Optimizer_Validation/`: original desktop and laptop output, including failed and corrected partial GPU collection tests. The laptop profile collection is not a completed 386-measurement profile.
- `Development_Smoke_Tests/`: development-environment test outputs, separate from the user's research results. These may contain test fixtures, tiny workloads, or failed experiments; never pool them with the main experiment data. Experiment 5 Source/example_results is also a development example, not the desktop study.
- `RECOVERY_MANIFEST.csv`: original archive/member (or loose filename), classification, byte size and SHA-256 for each recovered file.

## Recovery status

| Experiment | Recovered | Missing or caveat |
|---|---|---|
| 4B | Source and methodology | No original user result dataset located |
| 5 | Source; two sets of loose summary/calibration CSVs and graphs | Original desktop raw batches not located; source example results are local development output |
| 5B | Initial three-variant run, screening and confirmation, raw CSVs and figures; loose ranking | Loose ranking not assigned to a specific run |
| 5C | Screening and source | No separate full confirmation archive located |
| 5D | Original and corrected sources; local smoke tests separately | No full user results located |
| 5E | Full screening source and raw results (17,748 batches) | Negative findings retained |
| 5F | Prototype source, local smoke tests separately | Predecessor to Experiment 7; no separate full user dataset located |
| 6 | GPU baseline archive, source, telemetry | Baseline only; no end-to-end GPU hybrid measurements recovered |
| 7 | Smoke, full screening (6,120 batches), confirmation (987), result-check smoke, 500-round verification (29,000) | Result-check source originally limited rounds to 100; see reproduction note below |
| 8 | Pilot (46 CPU + 46 GPU rows), full (1,158 CPU + 1,158 GPU), confirmation (300 CPU + 300 GPU), original logs, source | Supplemental confirmation analysis output was not found in the uploaded ZIP; script retained |
| Optimizer | Desktop initial and all-five-mode runs, laptop CPU and two partial GPU tests | No completed laptop GPU profile; final application source is separate |

Experiments 1–4 were the teammate's original work; their files are not part of this recovery archive. Retain them in the existing repository. The file library search did not identify additional missing datasets. Check your Recycle Bin, local backup folders, teammate repository, and other conversation attachments if you need the missing early results.

## Reproduction and audit notes

- Experiment 7 result-check source was originally distributed with a 100-round cap. The user changed the upper bound from `a.rounds<=100` to `a.rounds<=1000` (and the corresponding error message) before running 500 rounds. The archived source is the original version, not a claimed recovered copy of the user's edited file. Apply the same change if reproducing the 500-round run.
- Experiment 7 Catena compilation required changing the BLAKE2 reference header alignment declaration from `ALIGN( 64 ) typedef struct` to `typedef struct ALIGN( 64 )` on the WSL system. Preserve the documented distinction between known-answer verification and input-sensitivity checks for optional KDFs.
- CPU-only concurrency measurements do not establish GPU or general cryptographic attack resistance. Experiment 8 results are measured on the selected RTX 4090 software/hardware stack. Negative results and partial/failing runs should remain clearly labeled.
- Keep original experiment-level audit notes as historical supporting records, but consolidate relied-upon AI outputs into the team's existing root AI_AUDIT.md for grading. The recovery process did not independently verify all historic claims or rerun the code.

## Before publishing to GitHub

Extract this archive locally. Copy the relevant folders into a new contribution branch, preserving teammate files. Review raw logs/JSON for personal file paths, hostnames, usernames and other machine-specific details before sharing publicly; these original files have not been sanitized. Keep the untouched recovery archive as a private backup. Avoid committing synthetic workload files if redundant or unnecessarily large, but retain enough data and source to reproduce the results and document any omitted files. Do not add virtual environments, compiled executables, caches or personal settings. Use the working v4.4 source folder and distribute the executable via a Release if appropriate. Check third-party notices and existing repository license before publication.
