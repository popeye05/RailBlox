"""Versioned, illustrative input contract; never a claimed CRIS API schema."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Factors(StrictModel):
    safety: int | None = Field(default=None, ge=0, le=5)
    security: int | None = Field(default=None, ge=0, le=5)
    operational: int | None = Field(default=None, ge=0, le=5)
    criticality: int | None = Field(default=None, ge=0, le=5)
    time_sensitivity: int | None = Field(default=None, ge=0, le=5)
    restrictions: int | None = Field(default=None, ge=0, le=5)
    combining: int | None = Field(default=None, ge=0, le=5)


class Period(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    section: str
    start: int = Field(ge=0, le=44640)
    end: int = Field(gt=0, le=46080)

    @model_validator(mode='after')
    def interval(self):
        if self.end <= self.start:
            raise ValueError('End must follow start')
        return self


class ExistingBlock(Period):
    kind: str = Field(default='Traffic', max_length=100)
    status: Literal['planned', 'active', 'completed', 'cancelled'] = 'planned'
    reason: str = Field(min_length=1, max_length=1000)


class Caution(Period):
    speed_kph: int | None = Field(default=None, gt=0, le=300)
    description: str = Field(min_length=1, max_length=1000)
    work_prohibited: bool = False


class Weather(Period):
    condition: Literal['clear', 'rain', 'heavy rain', 'storm', 'heat', 'fog']
    planning_hold: bool = False
    reason: str = Field(min_length=1, max_length=1000)


class History(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    section: str
    department: Literal['ENG', 'TRD', 'S&T']
    work_class: str
    planned_minutes: int = Field(gt=0, le=1440)
    actual_minutes: int = Field(gt=0, le=4320)
    delay_minutes: int = Field(default=0, ge=0, le=4320)
    completed_at: datetime
    weather: str = 'clear'
    narrative: str = Field(default='', max_length=5000)

    @model_validator(mode='after')
    def timezone(self):
        if self.completed_at.utcoffset() is None:
            raise ValueError('History timestamps need a timezone')
        return self


class Feed(StrictModel):
    source: Literal['COA', 'ROAMS', 'MIS/PAM', 'Weather']
    received_at: datetime
    max_age_minutes: int = Field(default=120, gt=0, le=44640)
    state: Literal['available', 'unavailable'] = 'available'

    @model_validator(mode='after')
    def timezone(self):
        if self.received_at.utcoffset() is None:
            raise ValueError('Feed timestamps need a timezone')
        return self


class Evidence(StrictModel):
    id: str
    snapshot_id: str
    division: str = Field(min_length=1, max_length=100)
    synthetic: bool = True
    as_of: datetime
    assessments: dict[str, Factors] = Field(default_factory=dict, max_length=1000)
    feeds: list[Feed] = Field(max_length=4)
    blocks: list[ExistingBlock] = Field(default_factory=list, max_length=1000)
    cautions: list[Caution] = Field(default_factory=list, max_length=1000)
    weather: list[Weather] = Field(default_factory=list, max_length=2000)
    history: list[History] = Field(default_factory=list, max_length=10000)

    @model_validator(mode='after')
    def valid_records(self):
        if self.as_of.utcoffset() is None:
            raise ValueError('Evidence as-of timestamp needs a timezone')
        sources = [f.source for f in self.feeds]
        if len(sources) != len(set(sources)):
            raise ValueError('Duplicate feed source')
        for records in [self.blocks, self.cautions, self.weather, self.history]:
            ids = [r.id for r in records]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate evidence record ID')
        if any(h.completed_at > self.as_of for h in self.history):
            raise ValueError('Historical outcomes cannot occur after the evidence time')
        return self


class EvidenceImport(StrictModel):
    expected_evidence: str
    evidence: Evidence


class RecommendRequest(StrictModel):
    snapshot_id: str
    evidence_id: str
    horizon: Literal[7, 30] = 7
    day: int = Field(default=0, ge=0, le=29)
    task_id: str | None = None
    window_id: str | None = None
    reason: str = Field(default='', max_length=1000)

    @model_validator(mode='after')
    def override(self):
        if bool(self.task_id) != bool(self.window_id):
            raise ValueError('Choose both a task and window for an override')
        if self.task_id and len(self.reason.strip()) < 3:
            raise ValueError('Explain the requested window modification')
        return self


class DecisionRequest(StrictModel):
    action: Literal['approve', 'reject']
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def reason_present(cls, value):
        if len(value.strip())<3:
            raise ValueError('Provide a meaningful review reason')
        return value


class OutcomeRequest(StrictModel):
    task_id: str
    actual_start: int = Field(ge=0, le=44640)
    actual_end: int = Field(gt=0, le=46080)
    observed_at: int = Field(ge=0, le=46080)
    delay_minutes: int = Field(default=0, ge=0, le=4320)
    weather: Literal['clear', 'rain', 'heavy rain', 'storm', 'heat', 'fog'] = 'clear'
    narrative: str = Field(min_length=3, max_length=5000)

    @model_validator(mode='after')
    def interval(self):
        if self.actual_end <= self.actual_start or self.actual_end > self.observed_at:
            raise ValueError('Actual end must follow start and not exceed the observation time')
        return self


class TextRequest(StrictModel):
    text: str = Field(min_length=3, max_length=5000)


class ReportRequest(StrictModel):
    recommendation_id: str
    kind: Literal['MIS', 'PAM'] = 'MIS'


class ReportReview(StrictModel):
    summary: str = Field(min_length=3, max_length=10000)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason', 'summary')
    @classmethod
    def text_present(cls, value):
        if len(value.strip())<3:
            raise ValueError('Review text cannot be blank')
        return value
