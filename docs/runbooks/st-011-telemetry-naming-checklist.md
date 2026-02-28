# ST-011 Telemetry Naming Checklist

Use this checklist when adding or updating telemetry for ST-011.

- [x] Metric name starts with `councilsense_`.
- [x] Metric name is snake_case and ends with `_total` (counter) or `_seconds` (duration histogram).
- [x] Metric name is unique across baseline telemetry definitions.
- [x] Required labels are bounded enums only.
- [x] Required labels include only `stage` and `outcome` for baseline metrics.
- [x] No high-cardinality IDs are used as metric labels.
- [x] Structured logs include required correlation keys: `city_id`, `meeting_id`, `run_id`, `dedupe_key`, `stage`, `outcome`.
