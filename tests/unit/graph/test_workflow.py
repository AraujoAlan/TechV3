from app.contracts.models import InterpretationResult, RequestContext
from app.graph.workflow import WorkflowDependencies, build_workflow
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
    def record_event(self, **kwargs): pass


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
