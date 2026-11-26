# Suggested AI audit entries — Experiment 5B

- AI contribution: generated expanded KDF cascade benchmark, variant-specific calibration, matched standalone controls, randomized batch scheduling, CSV/plot reporting and independent confirmation mode.
- Verification: syntax check; self-test against known answers and high-level argon2-cffi; all three variants passed small in-process worker/summary/chart checks. Optional bcrypt-PBKDF not installed in assistant environment. Full all-variant subprocess run not completed. Team must rerun on local hardware and record actual results.
- Limitation: matching latency is approximate; exclude unmatched configurations. Candidate selection is exploratory and subject to measurement noise and multiple comparisons. Confirm chosen configurations with the provided confirmation mode. Do not present a candidate flag as evidence of statistically significant or universally stronger security.
- Security/terminology: KDF cascades are not encryption. CPU throughput is a performance proxy, not a proof of password security or a GPU/ASIC benchmark. Argon2d's data-dependent accesses pose side-channel concerns. bcrypt-PBKDF is distinct from ordinary bcrypt.
- Research novelty: unverified; the contribution is a comparative empirical study, not a claim that cascades or these algorithms are new. Check literature independently.
- Team verification pending: install dependencies, run self-test, run screening and confirmation, inspect config and raw data files, repeat on second machine if available. Record outcome and any code changes in the team's AI_AUDIT.md.
