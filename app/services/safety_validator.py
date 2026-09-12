import re

from app.contracts.models import CritiqueResult, Source, ValidationResult


class DeterministicSafetyValidator:
    BLOCKED_PATTERNS = (r"\b\d+\s*(mg|ml)\b", r"\bposologia\b", r"\bprescrev", r"\bajuste de (dose|medica)")

    def validate(self, *, answer: str, sources: list[Source], has_individual_context: bool, is_critical: bool, critique: CritiqueResult) -> ValidationResult:
        violations: list[str] = []
        source_ids = {source.id for source in sources}
        cited = re.findall(r"\[S(\d+)\]", answer)
        for marker in cited:
            index = int(marker) - 1
            if index < 0 or index >= len(sources):
                violations.append("Citação não mapeada para fonte recuperada.")
        if not cited and sources:
            violations.append("Resposta sem citação de fontes recuperadas.")
        if any(re.search(pattern, answer, re.IGNORECASE) for pattern in self.BLOCKED_PATTERNS):
            violations.append("Linguagem de prescrição, dose ou ajuste autônomo detectada.")
        if is_critical and not re.search(r"avaliação humana|procure.*(serviço|atendimento)|escalon", answer, re.IGNORECASE):
            violations.append("Caso crítico sem escalonamento humano.")
        if not has_individual_context and re.search(r"seu prontuário|paciente identificado", answer, re.IGNORECASE):
            violations.append("Afirmação individual sem contexto autorizado.")
        for finding in critique.findings:
            if any(source_id not in source_ids for source_id in finding.source_ids):
                violations.append("Crítica cita fonte fora do contexto recuperado.")
        violations = list(dict.fromkeys(violations))
        if not violations:
            return ValidationResult(approved=True)
        return ValidationResult(approved=False, requires_revision=True, violations=violations, safe_message="Não foi possível fornecer uma resposta clínica segura nesta execução. Procure avaliação de um profissional de saúde.")
