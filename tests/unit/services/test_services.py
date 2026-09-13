import sqlite3

from app.contracts.models import AlertRequest, RequestContext
from app.services.alert_service import SqliteAlertService
from app.services.authorization import DemoAuthorizationService
from app.services.criticality import MaternalInfantCriticalityService
from app.services.medical_repository import MedicalRepositorySqlite


def repository():
    repo = MedicalRepositorySqlite(sqlite3.connect(":memory:")); repo.initialize(); return repo


def test_demo_authorization_does_not_expand_permissions():
    context = RequestContext(conversation_id="same", requester_id="demo", authorized_patient_ids={"P-042"})
    assert DemoAuthorizationService().is_patient_authorized(context, "P-042")
    assert not DemoAuthorizationService().is_patient_authorized(context, "P-101")


def test_synthetic_sources_and_criticality_are_versioned():
    repo = repository(); record = repo.get_patient_record("P-042"); exams = repo.get_pending_exams("P-042")
    assert record.source.id == "record:P-042:v1"
    assert MaternalInfantCriticalityService().evaluate(record=record, exams=exams, protocol=None).is_critical


def test_alert_is_idempotent():
    repo = repository(); service = SqliteAlertService(repo.connection)
    request = AlertRequest(audit_id="audit", patient_id="P-042", rule_code="MI-CRITICAL-001", rule_version="v1", reason="synthetic", idempotency_key="same")
    assert service.record_simulated_alert(request).alert_id == service.record_simulated_alert(request).alert_id
