from app.contracts.models import CriticalityResult, PatientRecord, PendingExam, ProtocolRecord


class MaternalInfantCriticalityService:
    """Pequenas regras explícitas; nunca infere criticidade com LLM."""
    RULE_VERSION = "v1"

    def evaluate(self, *, record: PatientRecord | None, exams: list[PendingExam], protocol: ProtocolRecord | None) -> CriticalityResult:
        text = " ".join([record.summary if record else "", *(exam.name for exam in exams)]).lower()
        if any(term in text for term in ("pressão grave", "sinais de alarme", "urgente", "critico")):
            return CriticalityResult(is_critical=True, rule_code="MI-CRITICAL-001", rule_version=self.RULE_VERSION, reason="Sinal crítico presente nos dados sintéticos.")
        return CriticalityResult(is_critical=False, rule_version=self.RULE_VERSION)
