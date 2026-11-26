# Proposed AI audit entries — Experiment 5
Merge into the team's actual AI_AUDIT.md after human verification. These are draft entries, not claims of teammate verification.

| Claim or output | Category | Verified? | How checked / next step |
|---|---|---|---|
| Python API calls for Argon2id, PBKDF2 and scrypt | nonexistent API/function | AI execution passed; team pending | Run --self-test locally; compare API docs. |
| Cascade output is reproducible and responds to password/salt changes | code that runs but is wrong | AI sanity checks passed; team pending | Run self-test and inspect stage order, salts and known-answer checks. Argon2 cross-check uses same native library, not independent implementation. |
| Equal authentication latency can be approximated through calibration | overclaim | Not demonstrated by final pilot | All six cascade configurations missed ±15% in included pilot. Rerun locally; exclude unmatched rows from equal-cost inference. |
| Stacking is more secure or novel | overclaim | Not established | CPU measurements do not establish attack resistance; conduct literature search and avoid unsubstantiated claims. |
| Peak RSS is the KDF's exact memory requirement | misstated result | Not true | RSS is sampled process memory including interpreter and library overhead; label accordingly. |
| Final full-mode benchmarks completed | misstated result | No | Only quick mode completed; a later experimental calibration change timed out and was reverted. Full mode is pending local execution. |
