# Suggested AI audit entries — review before merging into AI_AUDIT.md

| AI claim / output | Category | Verified? | How checked / next check |
|---|---|---|---|
| Extension uses the team's `argon2_hash(..., trace=...)` interface. | Nonexistent API or function | Source inspected; integration pending | Read `argon2_impl.py` on GitHub; run `--quick` locally. |
| Original uniform selector can retain an extra block. | Code that runs but is wrong | Source-level check | In `store_hybrid`, uniform selects `keep` spaced positions including 0; adding block 1 can increase size by one. Check actual set length for a chosen configuration. |
| Extension's model and retention functions pass toy and exact-budget checks. | Code that runs but is wrong | Yes, standalone tests only | `python exp4_extension.py --self-test` passed; compile check passed. Cross-check against original `attack_cost` is included in local integration run. |
| Argon2i graph is independent of password/salt for fixed parameters. | Misstated result | Specification-based expectation; empirical check pending | RFC 9106 section 3.4.1.2; compare graph fingerprints from the local run. |
| Input-sensitivity analysis is a candidate contribution. | Overclaim | Novelty unverified | Search related literature and confirm scope with instructor. Do not claim first-ever work. |
| Full-run outputs or empirical results. | Misstated result | Not yet verified | No full run in the AI environment. Run locally and use only generated data. |
