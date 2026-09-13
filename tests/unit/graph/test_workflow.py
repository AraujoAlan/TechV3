import pytest

from app.contracts.models import CritiqueFinding, CritiqueResult, InterpretationResult, PatientRecord, RequestContext, Source, ValidationResult
from app.graph.workflow import WorkflowDependencies, build_workflow, max_response_revisions
from app.llm.fakes import FakeFinalAnswerLLM, FakeGeneralLLM
from app.services.authorization import DemoAuthorizationService
from app.services.criticality import MaternalInfantCriticalityService
from app.services.safety_validator import DeterministicSafetyValidator


class Repository:
    def __init__(self): self.calls = []
    def get_patient_record(self, patient_id): self.calls.append("record"); return None
    def get_pending_exams(self, patient_id): self.calls.append("exams"); return []
    def get_protocol(self, condition): self.calls.append("protocol"); return None

class Alert:
    def record_simulated_alert(self, request): raise AssertionError("should not alert")
class Audit:
    def __init__(self): self.events = []
    def record_event(self, **kwargs): self.events.append(kwargs)


def run(interpretation, authorized=()):
    repository = Repository()
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), Audit(), FakeGeneralLLM(interpretation=interpretation), FakeFinalAnswerLLM(), DeterministicSafetyValidator())
    result = build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set(authorized))})
    return result, repository


def test_denied_patient_never_reads_repository():
    _, repository = run(InterpretationResult(candidate_patient_id="P-042"))
    assert repository.calls == []


def test_missing_patient_and_condition_clarifies_without_lookup():
    result, repository = run(InterpretationResult(requires_clarification=True))
    assert repository.calls == []
    assert "não foi possível" in result["final_answer"].lower()


def test_patient_without_condition_does_not_lookup_null_protocol():
    _, repository = run(InterpretationResult(candidate_patient_id="P-042"), authorized=("P-042",))
    assert "protocol" not in repository.calls


def test_condition_normalization_accepts_accented_puerperio():
    result, repository = run(InterpretationResult(candidate_condition="Puerpério"))

    assert result["condition"] == "puerperio"
    assert "protocol" in repository.calls


def test_audit_records_node_start_and_completion():
    repository = Repository()
    audit = Audit()
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), audit, FakeGeneralLLM(), FakeFinalAnswerLLM(), DeterministicSafetyValidator())

    build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set())})

    assert any(event["node"] == "interpret" and event["event"] == "started" for event in audit.events)
    assert any(event["node"] == "interpret" and event["event"] == "completed" for event in audit.events)


def test_audit_records_openai_usage_when_available():
    repository = Repository()
    audit = Audit()
    general_llm = FakeGeneralLLM()
    general_llm.last_usage = {"model": "gpt-4.1-mini", "input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), audit, general_llm, FakeFinalAnswerLLM(), DeterministicSafetyValidator())

    build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set())})

    usage = next(event for event in audit.events if event["node"] == "interpret" and event["event"] == "llm_usage")
    assert usage["details"]["total_tokens"] == 20


def test_audit_records_final_answer_provider_usage_when_available():
    repository = Repository()
    audit = Audit()
    final_llm = FakeFinalAnswerLLM()
    final_llm.last_usage = {"model": "gpt-4.1-mini", "input_tokens": 18, "output_tokens": 9, "total_tokens": 27}
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), audit, FakeGeneralLLM(interpretation=InterpretationResult(candidate_condition="puerperio")), final_llm, DeterministicSafetyValidator())

    build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set())})

    usage = next(event for event in audit.events if event["node"] == "generate" and event["event"] == "llm_usage")
    assert usage["details"]["total_tokens"] == 27


def test_audit_records_validation_violations():
    repository = Repository()
    audit = Audit()
    general_llm = FakeGeneralLLM(interpretation=InterpretationResult(candidate_condition="puerperio"), critique=CritiqueResult(findings=[CritiqueFinding(code="invalid", description="x", source_ids=["missing"])]))
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), audit, general_llm, FakeFinalAnswerLLM(answers=["Resposta sem fonte."]), DeterministicSafetyValidator())

    build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set())})

    validation = next(event for event in audit.events if event["node"] == "validate" and event["event"] == "completed")
    assert validation["details"]["violation_count"] == 1
    assert validation["details"]["violations"] == "Crítica cita fonte fora do contexto recuperado."


def test_critical_answer_gets_deterministic_human_escalation():
    class CriticalRepository(Repository):
        def get_patient_record(self, patient_id):
            self.calls.append("record")
            return PatientRecord(
                patient_id=patient_id,
                summary="Sinais de alarme documentados.",
                source=Source(id="record:P-042:v1", title="Prontuário", kind="prontuario"),
            )

    class RecordedAlert:
        def record_simulated_alert(self, request):
            return type("Recorded", (), {"status": "simulated_recorded"})()

    repository = CriticalRepository()
    final_llm = FakeFinalAnswerLLM(answers=["Há exame pendente [S1]."])
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), RecordedAlert(), Audit(), FakeGeneralLLM(interpretation=InterpretationResult(candidate_patient_id="P-042")), final_llm, DeterministicSafetyValidator())

    result = build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids={"P-042"})})

    assert "avaliação humana" in result["final_answer"].lower()
    assert result["revision_count"] == 0


class AlwaysRequiresRevision:
    def validate(self, **kwargs):
        return ValidationResult(approved=False, requires_revision=True, violations=["revisar"])


@pytest.mark.parametrize(("configured_limit", "expected_generations"), [("0", 1), ("2", 3)])
def test_workflow_respects_configured_revision_limit(monkeypatch, configured_limit, expected_generations):
    monkeypatch.setenv("MAX_RESPONSE_REVISIONS", configured_limit)
    repository = Repository()
    final_llm = FakeFinalAnswerLLM(answers=["rascunho"])
    deps = WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), Alert(), Audit(), FakeGeneralLLM(interpretation=InterpretationResult(candidate_condition="puerperio")), final_llm, AlwaysRequiresRevision())

    build_workflow(deps).invoke({"question": "teste", "request_context": RequestContext(conversation_id="c", requester_id="r", authorized_patient_ids=set())})

    assert len(final_llm.calls) == expected_generations


@pytest.mark.parametrize("value", ["-1", "invalido"])
def test_revision_limit_rejects_invalid_environment_value(monkeypatch, value):
    monkeypatch.setenv("MAX_RESPONSE_REVISIONS", value)

    with pytest.raises(ValueError, match="inteiro maior ou igual a zero"):
        max_response_revisions()
