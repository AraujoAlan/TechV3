from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RequestContext(BaseModel):
    conversation_id: str
    requester_id: str
    authorized_patient_ids: frozenset[str]
    mode: Literal["demo"] = "demo"


class Source(BaseModel):
    id: str
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"]


class PatientRecord(BaseModel):
    patient_id: str
    summary: str
    source: Source


class PendingExam(BaseModel):
    exam_id: str
    name: str
    requested_at: datetime | None = None
    source: Source


class ProtocolRecord(BaseModel):
    condition: str
    version: str
    summary: str
    source: Source


class CriticalityResult(BaseModel):
    is_critical: bool
    rule_code: str | None = None
    rule_version: str
    reason: str | None = None


class InterpretationResult(BaseModel):
    intent: str | None = None
    candidate_patient_id: str | None = None
    candidate_condition: str | None = None
    requires_clarification: bool = False
    clarification_request: str | None = None


class AnalysisFinding(BaseModel):
    summary: str
    source_ids: list[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    findings: list[AnalysisFinding] = Field(default_factory=list)


class CritiqueFinding(BaseModel):
    code: str
    description: str
    source_ids: list[str] = Field(default_factory=list)


class CritiqueResult(BaseModel):
    findings: list[CritiqueFinding] = Field(default_factory=list)


class AlertRequest(BaseModel):
    audit_id: str
    patient_id: str | None = None
    rule_code: str
    rule_version: str
    reason: str
    idempotency_key: str


class AlertRecord(BaseModel):
    alert_id: str
    idempotency_key: str
    created_at: datetime
    status: Literal["simulated_recorded"]


class ValidationResult(BaseModel):
    approved: bool
    requires_revision: bool = False
    violations: list[str] = Field(default_factory=list)
    safe_message: str | None = None
