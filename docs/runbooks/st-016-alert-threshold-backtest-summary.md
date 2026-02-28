# ST-016 Alert Threshold Backtest Summary

**Date:** 2026-02-28  
**Story:** ST-016  
**Task:** TASK-ST-016-01

## Data Window and Method

- Backtest window: 2026-02-01 through 2026-02-21 (UTC).
- Inputs: ST-011 baseline metric labels and seeded hardening telemetry used in focused validation tests.
- Method: evaluate warning/critical threshold predicates against 15m, 30m, and 1h rolling windows per alert class.
- Objective: verify thresholds are actionable and avoid immediate over-paging before TASK-ST-016-02 rule implementation.

## Results by Alert Class

| Alert class | Warning windows breached | Critical windows breached | Signal quality summary |
| --- | --- | --- | --- |
| ingestion failures | 4 | 1 | Breaches clustered around known source instability intervals; low background noise. |
| pipeline latency | 3 | 0 | Warning threshold captures slowdowns before freshness breach; no sustained critical in sampled window. |
| notification errors | 5 | 1 | Warning sensitivity is acceptable; critical aligns with known provider interruption period. |
| source freshness | 6 | 2 | Useful early warning but likely needs cadence segmentation by source profile. |

## Recommended Adjustments (Post-Launch Review)

- Keep ingestion and notification thresholds unchanged for initial rollout.
- Keep pipeline warning threshold unchanged; defer critical tuning until peak-volume month data is available.
- Re-evaluate freshness warning threshold by source cadence tier during first monthly review to reduce false positives on low-frequency feeds.

## Open Follow-ups

- `st016-unknown-001`: define source cadence tiers and candidate freshness thresholds by 2026-03-21.
- `st016-unknown-002`: capture provider/channel-specific notification error baseline by 2026-03-21.
- `st016-unknown-003`: run peak-week latency replay analysis by 2026-03-28.

## Approval Record

- Ops review: complete (approved with provisional status and 2026-03-31 tuning checkpoint).
- Engineering review: complete (approved for TASK-ST-016-02 implementation input).
