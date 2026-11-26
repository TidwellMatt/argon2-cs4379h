# AI audit supplement — Experiment 7 result checking

Suggested entries for the team to verify and incorporate into the shared audit. These are not a substitute for team verification.

| Claim | Category | Verified? | How checked / remaining check |
|---|---|---|---|
| The selection contains exactly the ten best hybrids and 19 deduplicated standalone controls from the supplied screening run. | Misstated result | Assistant checked; team review pending | Sort `ranking.csv` by raw product, compare the manifest against `configs.json`, verify source SHA-256 hashes. |
| A hybrid with a better product than one control does not necessarily beat the strongest control. | Code that runs but is wrong | Assistant regression passed; team review pending | Synthetic regression with two controls and one hybrid; inspect `pairwise_comparisons.csv`. |
| Repeated rounds quantify performance variability rather than proving cryptographic security. | Overclaim | Scope explicitly limited | Read the methodology and distinguish CPU throughput from actual attack security; no GPU or cracking measurements. |
| Optional yescrypt/Lyra2 output is deterministic and input-sensitive, but independent known-answer verification is pending. | Overclaim | Not independently verified | Run self-test on WSL and verify against independent upstream test vectors before treating the backends as cryptographically validated. |
| Full confirmation results are not available yet. | Misstated result | Pending | Run the frozen test on the same WSL environment and save the raw measurements; report all outcomes. |
