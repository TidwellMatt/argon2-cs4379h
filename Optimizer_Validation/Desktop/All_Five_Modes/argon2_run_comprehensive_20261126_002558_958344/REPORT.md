# Argon2id parameter recommendation

**Mode: Comprehensive analysis**
Test all eligible candidates; report tradeoffs and a Pareto frontier. Show the defense-first choice as a reference, not a universal winner.
Tested 49 of 49 eligible configurations; 16 independently confirmed.
Elapsed time: 251.3 seconds.
The highlighted recommendation is the defense-first choice; review the frontier for other tradeoffs.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m128_t5_p8 | 90.64 | 409.00 | 37.074 | yes |
| 2 | id_m128_t4_p8 | 73.06 | 527.00 | 38.502 | yes |
| 3 | id_m64_t6_p4 | 71.06 | 694.00 | 49.316 | yes |
| 4 | id_m64_t6_p8 | 51.85 | 701.00 | 36.345 | yes |
| 5 | id_m128_t3_p8 | 56.87 | 713.00 | 40.550 | no |
| 6 | id_m128_t3_p4 | 75.99 | 757.00 | 57.522 | no |
| 7 | id_m64_t5_p4 | 58.69 | 824.00 | 48.360 | yes |
| 8 | id_m64_t5_p2 | 96.80 | 834.00 | 80.733 | yes |
| 9 | id_m64_t5_p8 | 48.18 | 858.00 | 41.341 | yes |
| 10 | id_m64_t4_p8 | 34.55 | 1024.00 | 35.377 | yes |
Full confirmed ranking and 14 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**128 MiB, t=5, p=8**
PHC parameters: `m=131072,t=5,p=8`
Profile maximum observed: 409.00 H/s; minimum profile repetitions: 2.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 90.64 | 98.58 |
| cpu_ms | 609.38 | 666.67 |
| concurrent_hps | 14.76 | 14.58 |
| concurrent_p95_ms | 276.42 | 284.41 |
| rss_peak_mib | 551.78 | 551.81 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 90.64 | 36.43 |
| cpu_ms | 609.38 | 111.98 |
| concurrent_hps | 14.76 | 45.44 |
| concurrent_p95_ms | 276.42 | 92.31 |
| rss_peak_mib | 551.78 | 296.42 |
| GPU profile maximum H/s | 409.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
