# AI audit — Experiment 5F (append to team audit after checking)

| Claim / output | Category | Verification | How checked |
|---|---|---|---|
| Argon2 stays unchanged when another stage is added | code that runs but is wrong | locally checked | Config generator asserts the exact named fixed anchor is present in each cascade; no latency calibration |
| Latency-throughput score does not reward proportional increases in both defender and attacker time | overclaim | formula checked | Doubling single latency and halving throughput leaves product unchanged; metric is CPU parallel-scaling proxy only |
| Balloon reference implements published SHA256 vectors | misstated result | verified locally | Three known-answer tests from Nettle; native and Python both matched |
| yescrypt adapter | nonexistent API / code that runs but is wrong | partial | libxcrypt fallback passed deterministic/input-sensitivity checks locally; pyescrypt Windows adapter and independent known answers pending |
| Lyra2 and Catena PHS integration | nonexistent API / code that runs but is wrong | not verified end-to-end | Upstream headers reviewed; optional Linux build script and shared-library adapters not executed locally; missing methods are explicitly logged |
| Previous cipher/KDF cascade checks | code that runs but is wrong | local pass excluding bcrypt | Existing 5C known answers and cascade self-tests, 100 fixtures; bcrypt absent locally |
| Complete 5F results | misstated result | pending | Local 11-configuration smoke run, 22 batches; full run on user's hardware not performed |

No GPU cascade results are claimed. No novelty guarantee or production security claim. The score is a hardware and software-specific benchmark proxy; low throughput is not proof of resistance to optimized attacks. Verify optional source builds and record revisions before using them in the paper.
