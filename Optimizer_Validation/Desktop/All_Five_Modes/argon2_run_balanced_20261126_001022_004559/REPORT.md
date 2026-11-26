# Argon2id parameter recommendation

**Mode: Balanced performance**
Minimize confirmed median CPU latency (seconds) × stored maximum GPU H/s.
Tested 49 of 49 eligible configurations; 16 independently confirmed.
Elapsed time: 242.0 seconds.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m64_t6_p8 | 47.34 | 701.00 | 33.186 | yes |
| 2 | id_m64_t4_p8 | 34.26 | 1024.00 | 35.085 | yes |
| 3 | id_m128_t5_p8 | 87.77 | 409.00 | 35.898 | yes |
| 4 | id_m64_t5_p8 | 41.93 | 858.00 | 35.980 | yes |
| 5 | id_m64_t3_p8 | 26.14 | 1401.00 | 36.620 | yes |
| 6 | id_m128_t4_p8 | 72.02 | 527.00 | 37.952 | yes |
| 7 | id_m128_t3_p8 | 56.19 | 713.00 | 40.066 | no |
| 8 | id_m64_t6_p4 | 65.16 | 694.00 | 45.218 | yes |
| 9 | id_m64_t5_p4 | 57.21 | 824.00 | 47.139 | yes |
| 10 | id_m128_t4_p4 | 87.82 | 543.00 | 47.688 | yes |
Full confirmed ranking and 14 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**64 MiB, t=6, p=8**
PHC parameters: `m=65536,t=6,p=8`
Profile maximum observed: 701.00 H/s; minimum profile repetitions: 20.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 47.34 | 52.50 |
| cpu_ms | 278.12 | 351.56 |
| concurrent_hps | 25.68 | 25.15 |
| concurrent_p95_ms | 159.47 | 160.67 |
| rss_peak_mib | 296.61 | 296.63 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 47.34 | 35.71 |
| cpu_ms | 278.12 | 114.58 |
| concurrent_hps | 25.68 | 46.52 |
| concurrent_p95_ms | 159.47 | 88.82 |
| rss_peak_mib | 296.61 | 296.32 |
| GPU profile maximum H/s | 701.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
