# Argon2id parameter recommendation

**Mode: Maximum defense**
Minimize stored GPU H/s; stop at the first confirmed feasible configuration.
Tested 23 of 49 eligible configurations; 1 independently confirmed.
Elapsed time: 128.4 seconds.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m128_t5_p8 | 75.37 | 409.00 | 30.828 | yes |
Full confirmed ranking and 1 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**128 MiB, t=5, p=8**
PHC parameters: `m=131072,t=5,p=8`
Profile maximum observed: 409.00 H/s; minimum profile repetitions: 2.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 75.37 | 79.55 |
| cpu_ms | 552.08 | 578.12 |
| concurrent_hps | 16.04 | 15.29 |
| concurrent_p95_ms | 256.09 | 271.45 |
| rss_peak_mib | 552.06 | 552.07 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 75.37 | 32.96 |
| cpu_ms | 552.08 | 109.38 |
| concurrent_hps | 16.04 | 51.60 |
| concurrent_p95_ms | 256.09 | 80.00 |
| rss_peak_mib | 552.06 | 296.24 |
| GPU profile maximum H/s | 409.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
