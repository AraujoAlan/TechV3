from app.contracts.models import CritiqueResult, Source
from app.services.safety_validator import DeterministicSafetyValidator


def test_invalid_citation_requires_revision():
    result = DeterministicSafetyValidator().validate(answer="Use [S2].", sources=[Source(id="s1", title="x", kind="protocolo")], has_individual_context=False, is_critical=False, critique=CritiqueResult())
    assert not result.approved and result.requires_revision


def test_critical_answer_requires_human_escalation():
    result = DeterministicSafetyValidator().validate(answer="Fato [S1].", sources=[Source(id="s1", title="x", kind="protocolo")], has_individual_context=True, is_critical=True, critique=CritiqueResult())
    assert not result.approved
