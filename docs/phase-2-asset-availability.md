# Phase 2 — Asset Availability and Downtime Optimization

## Purpose

Phase 2 moves RailBLOX from a maintenance block planning prototype to an asset availability optimization system. The planner must choose maintenance work and block windows using the expected effect on critical infrastructure availability, while preserving safety, timetable, possession, resource, and officer-review controls.

The phase is complete only when the system can explain how each scheduled activity changes expected downtime and critical asset availability.

## Current baseline

The existing prototype already provides:

- CP-SAT scheduling through OR-Tools.
- Weekly and monthly planning horizons.
- Engineering, Traction Distribution, and Signal & Telecom work packages.
- Synthetic timetable, freight, block, resource, dependency, and protection data.
- Source CSV/JSON preview and immutable evidence snapshots.
- Officer validation, approval, outcomes, reports, audit, roles, and MFA.

The following are still prototype boundaries:

- TMS, SMMS, TDMS, and Control Office data are not live connections.
- Asset records describe canonical locations, not operational health.
- The objective does not yet contain asset uptime, downtime, failure probability, or availability terms.
- The local duration experiment is not a calibrated failure or risk model.

## Target decision model

Every maintenance task must be linked to one or more canonical assets. For each asset and planning horizon, calculate a baseline and planned availability estimate.

```text
expected_downtime_hours = failure_probability * expected_repair_hours
planned_downtime_hours = possession_hours + restoration_allowance
availability = 1 - (expected_downtime_hours + planned_downtime_hours) / horizon_hours
```

The formula is an engineering planning estimate. It must show its source data, timestamp, model version, and uncertainty; it must not be presented as a safety certification or a guaranteed forecast.

The solver should use a documented weighted objective:

```text
maximize
  criticality_weight * uptime_gain
  + urgency_weight * overdue_risk_reduction
  + service_weight * maintenance_value
  - downtime_weight * planned_downtime
  - disruption_weight * protected_train_impact
  - change_weight * changes_to_approved_work
```

Mandatory safety or legally required work remains a hard constraint. No objective weight may allow the solver to omit it. Weight values belong to a versioned policy configuration and require Officer review before use.

## Data contracts

### Canonical asset

Add an `AssetHealth` record to the evidence snapshot:

```json
{
  "asset_id": "AS-S1-UP-001",
  "asset_type": "track",
  "section": "S1-UP",
  "chainage_m": 2500,
  "criticality": "critical",
  "service_impact": 5,
  "operational_state": "degraded",
  "last_inspection_at": "2026-09-10T08:00:00+05:30",
  "maintenance_due_at": "2026-09-12T00:00:00+05:30",
  "failure_count_12m": 3,
  "exposure_hours_12m": 8760,
  "estimated_repair_hours": 4,
  "source": "SMMS",
  "source_record_id": "SMMS-123",
  "source_timestamp": "2026-09-10T08:05:00+05:30",
  "confidence": "review_required"
}
```

Use explicit enums for asset type, state, criticality, and confidence. Reject unknown units, negative durations, invalid dates, duplicate asset IDs, and source timestamps in the future.

### Maintenance task additions

Extend each task with:

- `asset_ids`: canonical assets affected by the activity.
- `criticality_override`: optional Officer-reviewed override with a reason.
- `maintenance_class`: preventive, corrective, inspection, statutory, or renewal.
- `overdue_since` and `due_at`.
- `expected_downtime_hours` and `restoration_hours`.
- `failure_risk_score` and `risk_model_version`.

Existing `asset_id` remains supported during migration and is converted to a one-item `asset_ids` list.

### Block and movement inputs

Every block window must retain its source ID, availability interval, affected sections, isolation group, preparation/restoration stages, and freshness timestamp. Timetable and goods-train occupancy records must identify whether they are observed, forecast, or synthetic.

## Integration sequence

Implement adapters behind one normalized interface:

```text
fetch_source(source, corridor, from_time, to_time) -> SourceBatch
normalize(SourceBatch) -> CanonicalSnapshotDelta
```

Build the adapters in this order:

1. TMS defects and overdue maintenance.
2. SMMS asset condition, inspection, and failure history.
3. TDMS traction and electrical maintenance.
4. Control Office timetable and goods-train forecast.
5. Block availability and possession updates.

Each adapter must define authentication, pagination, retry/backoff, rate limits, freshness limits, idempotency keys, schema version, and failure behavior. A failed source must mark its feed stale and block new recommendations when the affected safety or availability fields cannot be trusted.

Do not enable a connector with invented endpoints. The system owners must provide an authorized URL, schema example, credentials, refresh rules, and data owner for each source.

## Backend implementation slices

### Slice A — Asset health model

- Add Pydantic models and database persistence for asset health and availability estimates.
- Add snapshot validation and source freshness checks.
- Add asset-to-task and asset-to-section referential validation.
- Return asset health and uncertainty in the workspace API.

### Slice B — Availability analytics

- Implement deterministic baseline availability and planned availability calculations.
- Add a transparent priority score using criticality, overdue age, failure rate, service impact, and readiness.
- Keep model inputs and policy version alongside every recommendation.
- Add unit tests for missing, stale, conflicting, and low-confidence health data.

### Slice C — OR-Tools objective

- Add asset downtime and uptime-gain coefficients to each candidate task/window choice.
- Add shared-asset constraints so conflicting work is not double-counted.
- Preserve hard mandatory, safety, isolation, timetable, resource, dependency, and approved-commitment constraints.
- Return objective components and per-asset contribution in the saved plan.
- Add comparison output showing baseline availability, planned availability, downtime avoided, and critical assets improved.

### Slice D — Source adapters

- Add one adapter at a time using recorded, anonymized contract fixtures.
- Store raw source references separately from normalized records.
- Make imports idempotent and preserve immutable source timestamps.
- Add a dry-run preview and Officer confirmation before a source delta becomes planning evidence.

### Slice E — Operations dashboard

Add a dedicated Availability view with:

- Critical asset availability before and after the plan.
- Downtime avoided by task and block.
- Overdue critical maintenance.
- Stale or conflicting source feeds.
- Asset risk and confidence distribution.
- Weekly/monthly trend comparison.
- Exportable evidence and Officer review history.

## API additions

Add these authenticated endpoints:

```text
GET  /api/assets/health?snapshot_id=...
GET  /api/assets/{asset_id}/availability?snapshot_id=...
GET  /api/availability/summary?snapshot_id=...&horizon=7|30&day=...
POST /api/sources/{source}/sync/preview
POST /api/sources/{source}/sync/commit
```

Source sync preview and commit are Planner actions. Recommendations, validation, and benchmark runs retain their current Officer requirements. Any source delta that changes a critical asset or block must invalidate older recommendations.

## AI and ML policy

Phase 2 may use ML to estimate failure risk or repair duration, but the model must not silently override engineering rules. Begin with interpretable baselines:

- Failure rate with exposure normalization.
- Recency and overdue features.
- Historical duration regression.
- Calibrated uncertainty or an explicit `review_required` state.

Store model version, training cutoff, feature IDs, evaluation results, and data classification with each estimate. External LLM calls remain optional and must not receive operational data unless the configured data policy explicitly authorizes it. LLM output may explain a recommendation; it cannot select, approve, or dispatch work.

## Verification plan

Add automated tests for:

- Asset/task/source referential integrity.
- Stale and conflicting source data.
- Availability calculations with known expected results.
- Critical assets receiving higher priority under equal conditions.
- Downtime reduction appearing in objective components.
- Shared assets not being double-counted.
- Mandatory work remaining hard-constrained.
- Timetable and goods-train conflicts remaining hard-constrained.
- Weekly and monthly plans producing reproducible objective breakdowns.
- Role enforcement and Officer approval of availability-based recommendations.

Acceptance scenario:

1. Import two critical degraded assets, one overdue task, a timetable, and a goods-train forecast.
2. Generate weekly and monthly plans.
3. Confirm the plan schedules the highest availability-gain work that fits safe blocks.
4. Shorten a block and confirm the solver reports downtime and availability changes.
5. Introduce a new failure and confirm the old recommendation becomes stale.
6. Have an Officer validate and approve the plan.
7. Export the plan with source IDs, objective components, model version, and uncertainty.

## Deployment gate

Phase 2 is ready for a pilot only after the operational owner signs off the normalized data contracts, criticality policy, safety constraints, source freshness rules, and availability calculation. The current synthetic prototype may continue to be deployed as a demonstration, but it must continue to label all results as synthetic advisory planning.

