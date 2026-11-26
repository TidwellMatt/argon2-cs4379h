# Suggested AI audit entries — Experiment 5C

These are draft entries, not a substitute for team verification. Merge only after checking them and record the actual results.

| AI output / claim | Category | Verified? | How checked / next step |
|---|---|---|---|
| All ten listed cipher constructions work in cryptography | API/function | Locally verified | Ran synthetic encryption and cascade fixtures on cryptography 46.0.4; rerun self-test on Windows. |
| AES-CBC known answer and inherited KDF known answers match | Misstated result risk | Locally verified | Executed self-test; independently confirm standard vectors if relying on them. |
| Global ranking rejects a hybrid beating d but not tuned id | Code correctness | Locally verified | Synthetic ranking fixture; inspect actual ranking CSV after full run. |
| 234 default full-size configurations | Code/count | By inspection only | Count configs.json after calibration. |
| Smoke benchmark generates CSVs and graphs | Code correctness | Locally verified | 9 configs, 18 batches. Full matrix not run. |
| bcrypt-PBKDF path | API/function | Not verified here | Local bcrypt unavailable; install and rerun self-test. |
| A hybrid is stronger than standalone Argon2 | Overclaim | Not established | CPU throughput alone cannot show cryptographic security, GPU/ASIC resistance, or side-channel safety. |
| Cipher workloads are established password hashing methods | Overclaim | False if asserted | These are experimental synthetic constructions only. |
| Novelty of the experiment | Overclaim | Not established | Team must independently review prior literature. |
