"""Deterministic, explainable asset availability estimates.

These calculations are planning estimates for the synthetic prototype. They are
kept separate from the safety validator so an availability score can never
override an engineering or protection rule.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MODEL_VERSION = "availability-baseline-1.0"
AssetType = Literal["track", "ohe", "signal", "turnout", "power", "other"]
OperationalState = Literal["healthy", "degraded", "failed", "out_of_service"]
Criticality = Literal["critical", "high", "normal"]
Confidence = Literal["high", "medium", "review_required"]


class AssetHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=1, max_length=100)
    asset_type: AssetType
    section: str = Field(min_length=1, max_length=100)
    chainage_m: int = Field(ge=0)
    criticality: Criticality
    service_impact: int = Field(ge=0, le=5)
    operational_state: OperationalState
    last_inspection_at: str
    maintenance_due_at: str
    failure_count_12m: int = Field(ge=0)
    exposure_hours_12m: int = Field(gt=0)
    estimated_repair_hours: float = Field(gt=0, le=720)
    source: str = Field(min_length=1, max_length=50)
    source_record_id: str = Field(min_length=1, max_length=100)
    source_timestamp: str
    confidence: Confidence

    @field_validator("last_inspection_at", "maintenance_due_at", "source_timestamp")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("timestamp must include a timezone")
        except ValueError as exc:
            raise ValueError("timestamps must be ISO-8601") from exc
        return value

    @model_validator(mode="after")
    def source_is_not_future(self):
        source = datetime.fromisoformat(self.source_timestamp.replace("Z", "+00:00"))
        if source > datetime.now(timezone.utc):
            raise ValueError("source_timestamp cannot be in the future")
        return self


class AvailabilityEstimate(BaseModel):
    asset_id: str
    asset_type: str
    section: str
    criticality: str
    operational_state: str
    confidence: str
    source: str
    source_record_id: str
    source_timestamp: str
    model_version: str = MODEL_VERSION
    horizon_hours: float
    failure_probability: float
    planned_failure_probability: float
    expected_downtime_hours: float
    planned_downtime_hours: float
    baseline_availability: float
    planned_availability: float
    downtime_avoided_hours: float
    net_uptime_gain_hours: float
    scheduled_task_ids: list[str] = Field(default_factory=list)
    scheduled_block_ids: list[str] = Field(default_factory=list)
    uncertainty: str


def _as_health(asset: dict) -> AssetHealth:
    """Validate the normalized asset contract before calculating anything."""
    health = dict(asset.get("health") or {})
    # The outer asset keeps the canonical topology fields for existing clients;
    # health is a namespaced contract so older imports remain readable.
    return AssetHealth.model_validate({
        "asset_id": asset["id"],
        "section": asset["section"],
        "chainage_m": asset["chainage_m"],
        **health,
    })


def _round(value: float) -> float:
    return round(max(0.0, value), 3)


def _scheduled_reduction(task: dict) -> float:
    work_class = task.get("work_class", "inspection") if isinstance(task, dict) else task.work_class
    return {"corrective": 0.70, "statutory": 0.65, "renewal": 0.75, "preventive": 0.50}.get(work_class, 0.20)


def estimate(snapshot, horizon: int = 7, day: int = 0, plan: dict | None = None) -> list[AvailabilityEstimate]:
    horizon_hours = float(horizon * 24)
    start = day * 1440
    end = (day + horizon) * 1440
    tasks = {task.id: task for task in snapshot.tasks}
    assets = {health.asset_id: health for health in health_records(snapshot)}
    by_asset: dict[str, list[dict]] = {asset_id: [] for asset_id in assets}

    if plan:
        windows = {window.id: window for window in snapshot.windows}
        packages = {package["window_id"]: package for package in plan.get("packages", [])}
        for assignment in plan.get("assignments", []):
            task = tasks.get(assignment["task_id"])
            if not task or not (start <= assignment["start"] < end):
                continue
            window = windows.get(assignment["window_id"])
            package = packages.get(assignment["window_id"], {})
            closure_minutes = max(assignment["end"] - assignment["start"], 0)
            if package:
                closure_minutes = max(package.get("end", assignment["end"]) - package.get("start", assignment["start"]), closure_minutes)
            for asset_id in [task.asset_id]:
                if asset_id in by_asset:
                    by_asset[asset_id].append({
                        "task_id": task.id,
                        "window_id": assignment["window_id"],
                        "minutes": closure_minutes,
                        "reduction": _scheduled_reduction(task),
                        "window": window,
                    })

    estimates: list[AvailabilityEstimate] = []
    for asset_id, health in assets.items():
        rate = health.failure_count_12m / health.exposure_hours_12m
        failure_probability = min(rate * horizon_hours, 0.99)
        scheduled = by_asset[asset_id]
        # A shared block is counted once per asset, even if multiple tasks use it.
        unique_blocks: dict[str, dict] = {item["window_id"]: item for item in scheduled}
        reduction = max((item["reduction"] for item in scheduled), default=0.0)
        planned_failure_probability = failure_probability * (1.0 - reduction)
        expected = failure_probability * health.estimated_repair_hours
        planned_expected = planned_failure_probability * health.estimated_repair_hours
        planned_downtime = sum(item["minutes"] for item in unique_blocks.values()) / 60.0
        baseline_availability = 1.0 - expected / horizon_hours
        planned_availability = 1.0 - (planned_expected + planned_downtime) / horizon_hours
        estimates.append(AvailabilityEstimate(
            asset_id=health.asset_id,
            asset_type=health.asset_type,
            section=health.section,
            criticality=health.criticality,
            operational_state=health.operational_state,
            confidence=health.confidence,
            source=health.source,
            source_record_id=health.source_record_id,
            source_timestamp=health.source_timestamp,
            horizon_hours=horizon_hours,
            failure_probability=_round(failure_probability),
            planned_failure_probability=_round(planned_failure_probability),
            expected_downtime_hours=_round(expected),
            planned_downtime_hours=_round(planned_downtime + planned_expected),
            baseline_availability=_round(baseline_availability),
            planned_availability=_round(planned_availability),
            downtime_avoided_hours=_round(expected - planned_expected),
            net_uptime_gain_hours=_round(expected - planned_expected - planned_downtime),
            scheduled_task_ids=[item["task_id"] for item in scheduled],
            scheduled_block_ids=list(unique_blocks),
            uncertainty="Review required: synthetic baseline, not a failure forecast" if health.confidence == "review_required" else "Planning estimate; verify source before approval",
        ))
    return sorted(estimates, key=lambda row: ({"critical": 0, "high": 1, "normal": 2}[row.criticality], -row.net_uptime_gain_hours, row.asset_id))


def health_records(snapshot) -> list[AssetHealth]:
    records: list[AssetHealth] = []
    seen: set[str] = set()
    for asset in snapshot.assets:
        if asset.get("health") is None:
            continue
        if asset["id"] in seen:
            raise ValueError(f"Duplicate asset ID: {asset['id']}")
        record = _as_health(asset)
        if record.section != asset.get("section") or record.chainage_m != asset.get("chainage_m"):
            raise ValueError(f"Asset health topology mismatch: {record.asset_id}")
        seen.add(record.asset_id)
        records.append(record)
    return records


def summary(snapshot, horizon: int = 7, day: int = 0, plan: dict | None = None) -> dict:
    estimates = estimate(snapshot, horizon, day, plan)
    low_confidence = [row.asset_id for row in estimates if row.confidence == "review_required"]
    anchor = datetime.fromisoformat(snapshot.anchor.replace("Z", "+00:00"))
    overdue = [asset.asset_id for asset in health_records(snapshot) if datetime.fromisoformat(asset.maintenance_due_at.replace("Z", "+00:00")) < anchor]
    critical = [row for row in estimates if row.criticality == "critical"]
    return {
        "snapshot_id": snapshot.id,
        "plan_id": plan.get("id") if plan else None,
        "horizon_days": horizon,
        "day": day,
        "model_version": MODEL_VERSION,
        "as_of": snapshot.created_at,
        "synthetic": True,
        "estimates": [row.model_dump() for row in estimates],
        "metrics": {
            "assets": len(estimates),
            "critical_assets": len(critical),
            "critical_improved": sum(row.net_uptime_gain_hours > 0 for row in critical),
            "baseline_availability": _round(sum(row.baseline_availability for row in estimates) / len(estimates)) if estimates else None,
            "planned_availability": _round(sum(row.planned_availability for row in estimates) / len(estimates)) if estimates else None,
            "downtime_avoided_hours": _round(sum(row.downtime_avoided_hours for row in estimates)),
            "planned_downtime_hours": _round(sum(row.planned_downtime_hours for row in estimates)),
            "net_uptime_gain_hours": _round(sum(row.net_uptime_gain_hours for row in estimates)),
            "overdue_critical": len([asset_id for asset_id in overdue if any(row.asset_id == asset_id and row.criticality == "critical" for row in estimates)]),
        },
        "data_quality": {
            "low_confidence_assets": low_confidence,
            "missing_health_assets": [asset["id"] for asset in snapshot.assets if asset.get("health") is None],
            "stale_sources": [],
            "block_new_recommendation": bool(low_confidence),
        },
        "disclaimer": "Synthetic advisory planning estimate. It is not a safety certification, live asset condition, or guaranteed forecast.",
    }
