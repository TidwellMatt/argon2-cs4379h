# Argon2id parameter recommendation

**Mode: Resource efficiency**
Minimize confirmed median CPU time; break ties by Argon2 memory, then sampled RSS, within the required GPU throughput ceiling.
Tested 41 of 41 eligible configurations; 11 independently confirmed.
Elapsed time: 220.9 seconds.
Maximum stored GPU throughput: 1000 H/s.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m64_t5_p2 | 98.66 | 834.00 | 82.284 | yes |
| 2 | id_m64_t5_p4 | 58.20 | 824.00 | 47.960 | yes |
| 3 | id_m64_t6_p4 | 66.56 | 694.00 | 46.192 | yes |
| 4 | id_m64_t5_p8 | 42.73 | 858.00 | 36.664 | yes |
| 5 | id_m128_t3_p4 | 74.39 | 757.00 | 56.312 | no |
| 6 | id_m64_t6_p8 | 49.64 | 701.00 | 34.795 | yes |
| 7 | id_m128_t4_p4 | 94.84 | 543.00 | 51.496 | yes |
| 8 | id_m128_t3_p8 | 56.39 | 713.00 | 40.205 | no |
| 9 | id_m135_t4_p4 | 98.96 | 483.00 | 47.797 | yes |
| 10 | id_m128_t4_p8 | 70.94 | 527.00 | 37.388 | yes |
Full confirmed ranking and 9 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**64 MiB, t=5, p=2**
PHC parameters: `m=65536,t=5,p=2`
Profile maximum observed: 834.00 H/s; minimum profile repetitions: 2.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 98.66 | 98.96 |
| cpu_ms | 182.29 | 187.50 |
| concurrent_hps | 23.81 | 23.42 |
| concurrent_p95_ms | 172.45 | 176.08 |
| rss_peak_mib | 295.99 | 296.00 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 98.66 | 36.86 |
| cpu_ms | 182.29 | 109.38 |
| concurrent_hps | 23.81 | 46.01 |
| concurrent_p95_ms | 172.45 | 89.04 |
| rss_peak_mib | 295.99 | 296.29 |
| GPU profile maximum H/s | 834.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
