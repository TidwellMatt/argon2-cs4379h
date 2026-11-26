# AI audit additions: 5E

| Claim / change | Category | Verified? | How checked / limitation |
|---|---|---|---|
| Earlier symmetric latency gate excluded faster configurations even when concurrent throughput was lower. | Code that runs but is wrong for revised objective | Yes | Inspected 5D ranking; replaced primary gate with one-sided measured baseline ceiling and preserved symmetric analysis separately. |
| Faster standalone configurations remain eligible and can defeat hybrid candidates. | Code correctness | Yes (synthetic regression) | Fixture with 100 ms anchor, 70 ms standalone and 60 ms hybrid; checks comparator selection and eligibility; 111 ms hybrid rejected at 10% tolerance. |
| Zero CPU measurement cannot qualify a resource-matched candidate. | Code that runs but is wrong | Yes (regression) | Reused 5D timing fix and zero-value fixture. |
| Both hybrids and tunable standalone controls receive five target percentages. | Code correctness | Yes (plan inspection and regression) | 2,982 planned calibrations with all dependencies; 2,802 without bcrypt. Fixed controls retained once, duplicate tuned stages logged. |
| 5E runs end to end on the user's machine. | Unverified execution | Pending | Local smoke calibrated 33 configurations and reached 30/66 subprocess batches before execution timeout; separate real five-config in-process benchmark and five charts succeeded. User must run Windows smoke and full screening. |
| A hybrid that wins these benchmarks is more secure against GPU/ASIC attacks. | Overclaim | No | CPU synthetic throughput only; no custom GPU cascade implementation or proof of security. Novelty not established. |

Retain the team's original audit and AI_AUDIT_EXP5D.md for earlier work. Record actual command lines, failures, and verification outcomes from the user's machine.
