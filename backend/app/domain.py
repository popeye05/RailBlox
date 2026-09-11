from datetime import datetime, timezone
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Task(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100)
    department: Literal['ENG', 'TRD', 'S&T']
    asset_id: str
    section: str
    line: Literal['UP', 'DN'] = 'UP'
    chainage_m: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    duration: int = Field(gt=0, le=1440)
    mandatory: bool = False
    earliest: int = Field(ge=0)
    due: int
    weight: int = Field(default=10, gt=0, le=1000)
    priority: Literal['Critical', 'High', 'Normal'] = 'Normal'
    access: list[str] = Field(default_factory=lambda: ['traffic'])
    isolation: list[str] = Field(default_factory=list)
    resources: list[str]
    predecessors: list[str] = Field(default_factory=list)
    work_class: str = 'inspection'
    incompatible: list[str] = Field(default_factory=list)
    verified: bool = True
    ready: bool = True
    interruptible: bool = False
    started: bool = False
    source: str = 'TMS'
    source_record_id: str = ''
    source_timestamp: str = '2026-09-09T12:00:00+00:00'
    remarks: str = Field(default='', max_length=5000)
    deferrals: int = 0


class Window(BaseModel):
    id: str
    start: int
    end: int
    sections: list[str]
    access: list[str] = ['traffic', 'electrical']
    isolation: list[str]
    preparation: int = Field(default=10, ge=1)
    restoration: int = Field(default=10, ge=1)

    @model_validator(mode='after')
    def bounds(self):
        if self.end <= self.start:
            raise ValueError('Window end must be after start')
        return self


class Resource(BaseModel):
    id: str
    type: str = 'crew'
    capacity: int = Field(default=1, ge=1)
    availability: list[list[int]] = [[0, 43200]]
    setup: int = Field(default=0, ge=0)
    location: str = 'Depot'


class Snapshot(BaseModel):
    id: str
    corridor: str
    name: str
    anchor: str = '2026-09-09T18:30:00+00:00'
    created_at: str = Field(default_factory=utcnow)
    rule_version: str = 'SYNTHETIC-1'
    seed: int = 42
    tasks: list[Task]
    windows: list[Window]
    resources: list[Resource]
    sections: list[dict]
    assets: list[dict]
    movements: list[dict]
    protected_intervals: list[dict] = Field(default_factory=list)
    parent_id: str | None = None
    scenario: dict | None = None


class GenerateRequest(BaseModel):
    snapshot_id: str
    horizon: Literal[7, 30] = 7
    day: int = Field(default=0, ge=0, le=29)
    core_only: bool = False


class RevisionRequest(BaseModel):
    expected_snapshot: str
    task_ids: list[str] = []
    window_id: str | None = None
    task_id: str | None = None
    start: int | None = None
    release_unstarted: bool = False


class ApprovalRequest(BaseModel):
    expected_snapshot: str
    reason: str = Field(min_length=3, max_length=1000)


class ScenarioRequest(BaseModel):
    baseline_id: str
    kind: Literal['shorten', 'freight', 'crew', 'urgent', 'impossible', 'unresolved']
    target: str = ''
    minutes: int = Field(default=20, ge=1, le=1440)
    start: int = Field(default=120, ge=0, le=43200)
    end: int = Field(default=210, ge=1, le=44640)
    duration: int = Field(default=30, gt=0, le=1440)
    deadline: int = Field(default=240, ge=1, le=44640)


class AssignmentOutput(BaseModel):
    task_id: str
    window_id: str
    start: int
    end: int


class PackageOutput(BaseModel):
    id: str
    window_id: str
    sections: list[str]
    start: int
    end: int
    preparation_end: int
    restoration_start: int
    window_start: int
    window_end: int
    margin: int
    task_ids: list[str]


class ViolationOutput(BaseModel):
    rule_id: str
    records: list[str]
    message: str
    interval: list[int] | None = None


class ValidationOutput(BaseModel):
    model_config = ConfigDict(extra='allow')
    valid: bool
    label: str
    violations: list[ViolationOutput]


class MetricsOutput(BaseModel):
    scheduled: int
    eligible: int
    mandatory_met: int
    mandatory_required: int
    optional_scheduled: int
    service: int
    closed_section_minutes: int
    unresolved: int
    changed_assignments: int
    changed_task_ids: list[str]
    start_shift: int
    new_tasks: list[str]


class PlanOutput(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    snapshot_id: str
    parent_id: str | None
    horizon: Literal[7,30]
    day: int
    created_at: str
    solver_status: Literal['OPTIMAL','FEASIBLE','INFEASIBLE','UNKNOWN','MODEL_INVALID']
    assignments: list[AssignmentOutput]
    packages: list[PackageOutput]
    validation: ValidationOutput
    metrics: MetricsOutput
    unscheduled: list[dict[str,Any]]
    approval: Literal['proposed','approved','released']
    current: bool
    runtime_seconds: float
    objective_stages: list[dict[str,Any]]
    events: list[dict[str,Any]]
    core_only: bool


class TaskPage(BaseModel):
    items: list[Task]
    total: int
    page: int
    page_size: int


class RunOutput(BaseModel):
    id: str
    kind: str
    status: Literal['queued','running','succeeded','failed']
    created_at: str
    completed_at: str | None = None
    result_id: str | None = None
    error: str | None = None
