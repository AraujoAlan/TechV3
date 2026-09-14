from typing import TypedDict

from app.contracts.models import (AnalysisResult, CriticalityResult, CritiqueResult, PatientRecord, PendingExam, ProtocolRecord, RequestContext, Source)


class WorkflowState(TypedDict, total=False):
    question: str
    request_context: RequestContext
    audit_id: str
    patient_id: str | None
    condition: str | None
    authorized: bool
    record: PatientRecord | None
    exams: list[PendingExam]
    protocol: ProtocolRecord | None
    sources: list[Source]
    analysis: AnalysisResult
    criticality: CriticalityResult
    alert_status: str | None
    draft: str
    critique: CritiqueResult
    final_answer: str
    violations: list[str]
    revision_count: int
    error_code: str | None
