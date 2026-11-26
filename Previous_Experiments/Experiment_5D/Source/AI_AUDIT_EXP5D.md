# Suggested AI audit entries — Experiment 5D

These are AI-generated draft entries for the team to independently verify. Do not label local or GPU tests as passed until actually run.

| Claim | Category | Verified? | How to check |
|---|---|---|---|
| 5C hybrids used Argon2 p=1 while standalone controls included p=2,4 | Overclaim check | Source inspected by AI; team verification pending | Inspect source_5c_configs.json and original 5C results |
| 5D expands 186 hybrids across three lane settings plus 48 standalone controls | Code that runs but is wrong | AI configuration test passed; team pending | Run --self-test; inspect configs.json and count each family and lane |
| p=2,4 produces valid Argon2 outputs | Code correctness | AI reference cross-check passed for all variants; team pending | Run --self-test and verify reference tags |
| A lower-throughput hybrid that exceeds defender CPU budget is not a strict resource-budget winner | Code correctness | AI synthetic regression passed; team pending | Review summarize and run --self-test |
| A small CPU smoke experiment writes rankings/graphs | Code correctness | AI smoke passed without bcrypt; team pending | Run smoke on Windows; inspect outputs |
| GPU measurements represent actual GPU workloads | Overclaim | Not verified | Run optional GPU wrapper; verify device identity, parameter output and utilization logs |
| Hybrid GPU performance is known | Overclaim | False / not measured | Custom GPU kernels not provided; never claim GPU cascade speeds |
| Any hybrid is more secure than standard Argon2 | Overclaim | Not established | CPU benchmark is a performance signal; side-channel/cryptanalysis and GPU evaluation required |

Limitations/failures: 5C unequal p search and CPU-only measurements were identified as interpretation problems. 5D broadens CPU search and separates optional GPU baseline rather than claiming that CPU workload simulates GPU hardware. Bcrypt and full 5D and GPU tests remain pending. No novelty guarantee. Team should record actual commands, outputs, and corrections after verification.

### Timing hotfix
Original AI-generated code divided by a zero CPU-time measurement on Windows after the smoke benchmark. Corrected by extending batches and rejecting invalid resource comparisons; regression test injects zero CPU timings. Local smoke and self-tests passed with bcrypt excluded. Windows rerun pending.
