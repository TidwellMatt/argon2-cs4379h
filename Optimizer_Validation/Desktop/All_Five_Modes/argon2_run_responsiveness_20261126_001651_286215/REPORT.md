# Argon2id parameter recommendation

**Mode: Maximum responsiveness**
Minimize confirmed median CPU latency within the required GPU throughput ceiling.
Tested 41 of 41 eligible configurations; 11 independently confirmed.
Elapsed time: 215.8 seconds.
Maximum stored GPU throughput: 1000 H/s.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m64_t5_p8 | 43.84 | 858.00 | 37.615 | yes |
| 2 | id_m64_t6_p8 | 45.79 | 701.00 | 32.099 | yes |
| 3 | id_m128_t3_p8 | 56.03 | 713.00 | 39.951 | no |
| 4 | id_m64_t5_p4 | 56.09 | 824.00 | 46.221 | yes |
| 5 | id_m128_t4_p8 | 62.18 | 527.00 | 32.771 | yes |
| 6 | id_m64_t6_p4 | 63.02 | 694.00 | 43.734 | yes |
| 7 | id_m128_t3_p4 | 71.75 | 757.00 | 54.318 | no |
| 8 | id_m135_t4_p4 | 77.30 | 483.00 | 37.334 | yes |
| 9 | id_m128_t5_p8 | 84.51 | 409.00 | 34.563 | yes |
| 10 | id_m128_t4_p4 | 90.46 | 543.00 | 49.121 | yes |
Full confirmed ranking and 9 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**64 MiB, t=5, p=8**
PHC parameters: `m=65536,t=5,p=8`
Profile maximum observed: 858.00 H/s; minimum profile repetitions: 20.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 43.84 | 45.87 |
| cpu_ms | 284.38 | 343.75 |
| concurrent_hps | 29.69 | 28.64 |
| concurrent_p95_ms | 139.16 | 147.96 |
| rss_peak_mib | 296.28 | 296.29 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 43.84 | 39.77 |
| cpu_ms | 284.38 | 135.42 |
| concurrent_hps | 29.69 | 45.05 |
| concurrent_p95_ms | 139.16 | 91.21 |
| rss_peak_mib | 296.28 | 295.93 |
| GPU profile maximum H/s | 858.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
