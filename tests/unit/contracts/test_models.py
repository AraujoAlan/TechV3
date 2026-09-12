from app.contracts.models import RequestContext, Source


def test_contract_models_do_not_require_runtime_dependencies():
    context = RequestContext(conversation_id="c-1", requester_id="demo", authorized_patient_ids={"P-042"})
    source = Source(id="protocol:hipertensao-gestacional:v1", title="Protocolo", kind="protocolo")
    assert context.mode == "demo"
    assert source.id.endswith(":v1")
