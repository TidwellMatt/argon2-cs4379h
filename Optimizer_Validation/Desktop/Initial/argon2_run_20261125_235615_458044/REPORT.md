# Argon2id parameter recommendation

Tested 17 of 49 policy-eligible configurations.

**128 MiB, t=6, p=8**
PHC parameters: `m=131072,t=6,p=8`
Profile maximum observed: 341.00 H/s; minimum profile repetitions: 2.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 88.52 | 91.49 |
| cpu_ms | 604.17 | 640.62 |
| concurrent_hps | 13.88 | 13.76 |
| concurrent_p95_ms | 294.62 | 301.83 |
| rss_peak_mib | 551.93 | 552.04 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 88.52 | 31.50 |
| cpu_ms | 604.17 | 120.54 |
| concurrent_hps | 13.88 | 52.91 |
| concurrent_p95_ms | 294.62 | 77.03 |
| rss_peak_mib | 551.93 | 296.41 |
| GPU profile maximum H/s | 341.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
