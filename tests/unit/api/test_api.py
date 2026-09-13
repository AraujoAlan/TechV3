import os

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.graph.workflow import SAFE_LIMITATION


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CLINICAL_DATABASE", str(tmp_path / "api_demo.db"))
    monkeypatch.setenv("API_USE_FAKES", "true")
    monkeypatch.setenv("DEMO_REQUESTER_ID", "demo-clinician")
    monkeypatch.setenv("DEMO_AUTHORIZED_PATIENT_IDS", "P-042")
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_returns_ok_without_loading_models(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "demo"}


def test_chat_authorized_p042_returns_answer_sources_and_alert(client):
    response = client.post(
        "/api/chat",
        json={"question": "Paciente P-042 com hipertensão gestacional tem exames pendentes?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "completed"
    assert body["answer"]
    assert body["answer"] != SAFE_LIMITATION
    assert body["audit_id"]
    assert len(body["sources"]) >= 1
    assert body["alert"] == {"status": "simulated_recorded"}
    assert all(key in body["sources"][0] for key in ("id", "title", "kind"))
    # Contrato público: sem rascunho, tools ou violações.
    assert "draft" not in body
    assert "toolCalls" not in body
    assert "violations" not in body


def test_chat_unauthorized_returns_limited_without_clinical_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("CLINICAL_DATABASE", str(tmp_path / "api_denied.db"))
    monkeypatch.setenv("API_USE_FAKES", "true")
    monkeypatch.setenv("DEMO_AUTHORIZED_PATIENT_IDS", "")
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/chat",
            json={"question": "Paciente P-042 com hipertensão gestacional tem exames pendentes?"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "limited"
    assert body["answer"] == SAFE_LIMITATION
    assert body["sources"] == []
    assert body["alert"] is None


def test_chat_unknown_patient_returns_limited_without_enumeration(client):
    response = client.post(
        "/api/chat",
        json={"question": "Paciente P-999 com hipertensão gestacional tem exames pendentes?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "limited"
    assert body["answer"] == SAFE_LIMITATION
    assert body["sources"] == []


def test_chat_rejects_empty_question(client):
    response = client.post("/api/chat", json={"question": "   "})
    assert response.status_code == 422


def test_chat_rejects_missing_question(client):
    response = client.post("/api/chat", json={})
    assert response.status_code == 422


def test_chat_does_not_accept_client_authorization(client):
    """Mesmo se o cliente enviar campos de auth, a resposta usa só o principal do servidor."""
    response = client.post(
        "/api/chat",
        json={
            "question": "Paciente P-042 com hipertensão gestacional tem exames pendentes?",
            "authorized_patient_ids": ["P-999"],
            "requester_id": "attacker",
        },
    )
    assert response.status_code == 200
    body = response.json()
    # Com DEMO_AUTHORIZED_PATIENT_IDS=P-042 o fluxo autorizado segue completo.
    assert body["outcome"] == "completed"
    assert body["alert"] == {"status": "simulated_recorded"}


def test_audit_id_is_returned(client):
    response = client.post(
        "/api/chat",
        json={"question": "Quais sinais exigem atenção na hipertensão gestacional?"},
    )
    assert response.status_code == 200
    assert response.json()["audit_id"]
