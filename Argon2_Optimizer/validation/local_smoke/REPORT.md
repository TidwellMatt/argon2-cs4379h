# Argon2id parameter recommendation

Tested 1 of 16 policy-eligible configurations.

**64 MiB, t=6, p=4**
PHC parameters: `m=65536,t=6,p=4`
Profile maximum observed: 694.00 H/s; minimum profile repetitions: 2.

| CPU metric | Median | Conservative observed bound |
|---|---:|---:|
| latency_ms | 88.67 | 93.20 |
| cpu_ms | 135.25 | 156.18 |
| concurrent_hps | 11.10 | 10.42 |
| concurrent_p95_ms | 91.17 | 101.02 |
| rss_peak_mib | 161.34 | 161.34 |

## RFC low-memory reference (measured locally)

| Metric | Recommendation | Reference |
|---|---:|---:|
| latency_ms | 88.67 | 48.68 |
| cpu_ms | 135.25 | 76.44 |
| concurrent_hps | 11.10 | 20.16 |
| concurrent_p95_ms | 91.17 | 52.34 |
| rss_peak_mib | 161.34 | 161.58 |
| GPU profile maximum H/s | 694.00 | 1402.00 |

## Limitations
Empirical GPU profile maximum is not an upper bound on future attackers. CPU bounds are observed round extrema, not statistical confidence bounds. Screening can exclude feasible candidates. No universal security or global optimality claim.

See recommendation.json for profile provenance, reference comparison and complete numeric results.
