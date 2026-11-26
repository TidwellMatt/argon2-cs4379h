# Argon2id parameter recommendation

**Mode: Maximum defense**
Minimize stored GPU H/s; stop at the first confirmed feasible configuration.
Tested 32 of 49 eligible configurations; 1 independently confirmed.
Elapsed time: 260.2 seconds.

## Confirmed candidates (top 10 by selected objective)

| Rank | Configuration | CPU ms (latency) | GPU H/s | Latency × H/s (seconds) | Pareto |
|---:|---|---:|---:|---:|---|
| 1 | id_m64_t6_p8 | 82.82 | 701.00 | 58.060 | yes |
Full confirmed ranking and 1 non-dominated candidates among confirmed results are in confirmed_ranking.csv and pareto_frontier.csv.

**64 MiB, t=6, p=8**
PHC parameters: `m=65536,t=6,p=8`
Profile maximum observed: 701.00 H/s; minimum profile repetitions: 20.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 82.82 | 89.92 |
| cpu_ms | 26.04 | 62.50 |
| concurrent_hps | 13.07 | 12.81 |
| concurrent_p95_ms | 320.74 | 340.41 |
| rss_peak_mib | 291.16 | 291.35 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 82.82 | 71.34 |
| cpu_ms | 26.04 | 10.42 |
| concurrent_hps | 13.07 | 22.24 |
| concurrent_p95_ms | 320.74 | 195.62 |
| rss_peak_mib | 291.16 | 291.74 |
| GPU profile maximum H/s | 701.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
