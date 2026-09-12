from app.contracts.errors import FinalAnswerModelUnavailable, GeneralLLMUnavailable
from app.contracts.models import AnalysisResult, CritiqueResult, InterpretationResult


class FakeGeneralLLM:
    def __init__(self, interpretation: InterpretationResult | None = None, analysis: AnalysisResult | None = None, critique: CritiqueResult | None = None, fail: bool = False):
        self.interpretation = interpretation or InterpretationResult(requires_clarification=True, clarification_request="Informe paciente ou condição.")
        self.analysis_result = analysis or AnalysisResult()
        self.critique_result = critique or CritiqueResult()
        self.fail = fail

    def interpret(self, *, question: str) -> InterpretationResult:
        if self.fail: raise GeneralLLMUnavailable("Fake indisponível")
        return self.interpretation

    def analyze(self, **kwargs) -> AnalysisResult:
        if self.fail: raise GeneralLLMUnavailable("Fake indisponível")
        return self.analysis_result

    def critique(self, **kwargs) -> CritiqueResult:
        if self.fail: raise GeneralLLMUnavailable("Fake indisponível")
        return self.critique_result


class FakeFinalAnswerLLM:
    def __init__(self, answers: list[str] | None = None, fail: bool = False):
        self.answers = answers or ["Resposta sintética baseada no contexto recuperado [S1]. Procure avaliação humana."]
        self.calls: list[dict] = []
        self.fail = fail

    def generate(self, **kwargs) -> str:
        if self.fail: raise FinalAnswerModelUnavailable("Fake indisponível")
        self.calls.append(kwargs)
        return self.answers[min(kwargs["revision_attempt"], len(self.answers) - 1)]
