from app.contracts.models import Source
from app.llm.factory import (
    build_final_answer_user_prompt,
    normalize_source_citations,
    sanitize_generated_answer,
)


def _sources(*titles: str) -> list[Source]:
    return [
        Source(id=f"src:{index}", title=title, snippet=title, kind="protocolo")
        for index, title in enumerate(titles, start=1)
    ]


def test_build_final_answer_user_prompt_lists_allowed_markers():
    prompt = build_final_answer_user_prompt(
        question="Pergunta",
        context="[S1] fato",
        sources=_sources("A", "B"),
        revision_violations=[],
        revision_attempt=0,
    )
    assert "Citacoes permitidas" in prompt
    assert "[S1], [S2]" in prompt
    assert "Pergunta: Pergunta" in prompt
    assert "objetiva" in prompt.lower()


def test_normalize_source_citations_strips_invalid_and_keeps_valid():
    answer = "Achado clinico [S1] e ruido [S9]."
    result = normalize_source_citations(answer, _sources("A", "B"))
    assert "[S1]" in result
    assert "[S9]" not in result


def test_normalize_source_citations_appends_markers_when_missing():
    result = normalize_source_citations("Texto sem marcadores.", _sources("A", "B", "C"))
    assert result.endswith("[S1] [S2] [S3]")
    assert "Texto sem marcadores." in result


def test_normalize_source_citations_removes_markers_without_sources():
    result = normalize_source_citations("Texto [S1] solto.", [])
    assert result == "Texto solto."


def test_sanitize_generated_answer_strips_think_and_role_echo():
    raw = (
        "Primeira parte descartavel.\n"
        "assistant\n"
        "<think>\nraciocinio interno\n</think>\n"
        "Sim: ha exame pendente de pressao grave [S2]."
    )
    assert sanitize_generated_answer(raw) == "Sim: ha exame pendente de pressao grave [S2]."


def test_normalize_source_citations_keeps_last_assistant_turn():
    raw = "Eco antigo.\nassistant\nHa exame pendente [S2]."
    result = normalize_source_citations(raw, _sources("A", "B", "C"))
    assert result.startswith("Ha exame pendente")
    assert "[S2]" in result
    assert "Eco antigo" not in result
