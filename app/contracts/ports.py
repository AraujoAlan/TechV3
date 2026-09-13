from typing import Protocol

from .models import (
    AlertRecord, AlertRequest, AnalysisResult, CriticalityResult, CritiqueResult,
    InterpretationResult, PatientRecord, PendingExam, ProtocolRecord,
    RequestContext, Source, ValidationResult,
)


class AuthorizationService(Protocol):
    def is_patient_authorized(self, context: RequestContext, patient_id: str) -> bool: ...


class MedicalRepository(Protocol):
    def get_patient_record(self, patient_id: str) -> PatientRecord | None: ...
    def get_pending_exams(self, patient_id: str) -> list[PendingExam]: ...
    def get_protocol(self, condition: str) -> ProtocolRecord | None: ...


class CriticalityService(Protocol):
    def evaluate(self, *, record: PatientRecord | None, exams: list[PendingExam], protocol: ProtocolRecord | None) -> CriticalityResult: ...


class AlertService(Protocol):
    def record_simulated_alert(self, request: AlertRequest) -> AlertRecord: ...


class AuditLogger(Protocol):
    def record_event(self, *, audit_id: str, event: str, node: str, details: dict[str, str | int | float | bool | None], idempotency_key: str) -> None: ...


class GeneralLLM(Protocol):
    def interpret(self, *, question: str) -> InterpretationResult: ...
    def analyze(self, *, question: str, context: str, sources: list[Source]) -> AnalysisResult: ...
    def critique(self, *, question: str, answer: str, sources: list[Source], has_individual_context: bool, is_critical: bool) -> CritiqueResult: ...


class FinalAnswerLLM(Protocol):
    def generate(self, *, question: str, context: str, sources: list[Source], revision_violations: list[str], revision_attempt: int) -> str: ...


class SafetyValidator(Protocol):
    def validate(self, *, answer: str, sources: list[Source], has_individual_context: bool, is_critical: bool, critique: CritiqueResult) -> ValidationResult: ...
