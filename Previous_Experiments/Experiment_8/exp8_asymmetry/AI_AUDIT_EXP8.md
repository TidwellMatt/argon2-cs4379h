# AI audit — Experiment 8

AI assisted with experiment design, Python implementation, synthetic fixture generation, measurement extraction, statistical analysis and documentation. This is a new experiment, not a modification of Argon2.

Verified from primary sources: RFC 9106 recommends Argon2id with 2 GiB/t1/p4 and 64 MiB/t3/p4. Hashcat v8.0.0 mode 34000 accepts Argon2d/i/id and encodes m/t/p, v19, salt and digest in the PHC string. The built-in benchmark is fixed; parameter-specific inputs are necessary. Source code defines running status 3, exhausted 5, runtime abort 11 and per-device JSON speed in H/s. See README for exact links. Hashcat's source also includes an official Argon2id known-input vector, checked locally with argon2-cffi.

Verified from supplied Experiment 7 500-round CSV: best standalone configurations per variant are Argon2i 256 MiB/t6/p4, Argon2d 256 MiB/t6/p4, Argon2id 128 MiB/t6/p4. Included as controls along with tuned anchors. No earlier CPU throughput measurement is used as GPU data.

Local tests completed (Linux environment, not user's GPU): Python self-test; actual small CPU benchmark; simulated Hashcat subprocess outputs for synthetic known-input verification and sustained-speed parsing; CSV, analysis, graph output on temporary mock data. No fabricated GPU measurements are included in this package. CUDA/Hashcat command invocation, status output and VRAM telemetry on the user's Windows installation remain unverified until the pilot. The local benchmark does not predict user's CPU performance. Full grid and confirmation have not been executed. Student should record any failures, changes, driver version, results and independent verification before citing claims. The student's actual experiment output is the evidence, not the hypothetical examples in chat.

Important caveats: single hardware pair; no universal security claim; same-variant analysis; CPU login proxy; GPU H/s depends on backend and implementation; unadjusted bootstrap intervals; no positive-result guarantee; no novelty claim about parameter tuning itself. No external account credentials or target hashes used.
