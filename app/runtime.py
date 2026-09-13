"""Composição compartilhada das dependências do workflow (CLI e API)."""

from __future__ import annotations

import os
import re

from app.contracts.models import InterpretationResult
from app.graph.workflow import WorkflowDependencies
from app.llm.factory import OpenAIFinalAnswerLLM, OpenAIGeneralLLM, QwenLoraFinalAnswerLLM
from app.llm.fakes import FakeFinalAnswerLLM, FakeGeneralLLM
from app.services.alert_service import SqliteAlertService
from app.services.audit_logger import SqliteAuditLogger
from app.services.authorization import DemoAuthorizationService
from app.services.criticality import MaternalInfantCriticalityService
from app.services.medical_repository import MedicalRepositorySqlite
from app.services.safety_validator import DeterministicSafetyValidator


def build_final_answer_llm():
    provider = os.getenv("FINAL_ANSWER_PROVIDER", "qwen").lower()
    if provider == "qwen":
        return QwenLoraFinalAnswerLLM()
    if provider == "openai":
        return OpenAIFinalAnswerLLM()
    raise ValueError("FINAL_ANSWER_PROVIDER deve ser 'qwen' ou 'openai'")


def build_dependencies(
    database: str,
    use_fakes: bool,
    *,
    check_same_thread: bool = True,
) -> WorkflowDependencies:
    repository = MedicalRepositorySqlite.open(database, check_same_thread=check_same_thread)
    repository.initialize()
    connection = repository.connection
    general = FakeGeneralLLM() if use_fakes else OpenAIGeneralLLM()
    final = FakeFinalAnswerLLM() if use_fakes else build_final_answer_llm()
    return WorkflowDependencies(
        DemoAuthorizationService(),
        repository,
        MaternalInfantCriticalityService(),
        SqliteAlertService(connection),
        SqliteAuditLogger(connection),
        general,
        final,
        DeterministicSafetyValidator(),
    )


def interpretation_from_question(question: str) -> InterpretationResult:
    """Heurística determinística usada apenas com FakeGeneralLLM (CLI/API demo)."""
    patient_match = re.search(r"P-\d+", question)
    lowered = question.lower()
    condition = "hipertensao-gestacional" if "hipertens" in lowered else None
    if "puerper" in lowered:
        condition = "puerperio"
    has_anchor = patient_match is not None or condition is not None
    return InterpretationResult(
        candidate_patient_id=patient_match.group(0) if patient_match else None,
        candidate_condition=condition,
        requires_clarification=not has_anchor,
    )


def prepare_fake_interpretation(deps: WorkflowDependencies, question: str) -> None:
    general = deps.general_llm
    if isinstance(general, FakeGeneralLLM):
        general.interpretation = interpretation_from_question(question)
