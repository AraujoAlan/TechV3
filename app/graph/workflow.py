import os
import re
import unicodedata
import uuid
from dataclasses import dataclass

from langgraph.graph import END, START, StateGraph

from app.contracts.errors import WorkflowServiceError
from app.contracts.models import AlertRequest, CriticalityResult, CritiqueResult, InterpretationResult, Source
from app.contracts.ports import AlertService, AuditLogger, AuthorizationService, CriticalityService, FinalAnswerLLM, GeneralLLM, MedicalRepository, SafetyValidator
from .state import WorkflowState

SAFE_LIMITATION = "Não foi possível fornecer uma resposta clínica segura nesta execução. Procure avaliação de um profissional de saúde."
CRITICAL_ESCALATION = "Como há sinais de alarme no contexto, recomenda-se busca imediata de avaliação humana."


def max_response_revisions() -> int:
    value = os.getenv("MAX_RESPONSE_REVISIONS", "1")
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError("MAX_RESPONSE_REVISIONS deve ser um inteiro maior ou igual a zero") from error
    if result < 0:
        raise ValueError("MAX_RESPONSE_REVISIONS deve ser um inteiro maior ou igual a zero")
    return result


@dataclass(frozen=True)
class WorkflowDependencies:
    authorization: AuthorizationService
    repository: MedicalRepository
    criticality: CriticalityService
    alerts: AlertService
    audit: AuditLogger
    general_llm: GeneralLLM
    final_answer_llm: FinalAnswerLLM
    validator: SafetyValidator
    condition_catalog: frozenset[str] = frozenset({"hipertensao-gestacional", "puerperio"})


def _sources(*items) -> list[Source]:
    result: list[Source] = []
    for item in items:
        if item is None: continue
        source = item.source if hasattr(item, "source") else item
        if source.id not in {existing.id for existing in result}: result.append(source)
    return result


def normalize_condition(candidate: str | None, catalog: frozenset[str]) -> str | None:
    """Aceita variações de acento, espaço e sublinhado sem ampliar o catálogo."""
    if not candidate:
        return None
    normalized = unicodedata.normalize("NFKD", candidate).encode("ascii", "ignore").decode().lower().strip()
    normalized = re.sub(r"[\s_]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized)
    return normalized if normalized in catalog else None


def build_workflow(deps: WorkflowDependencies):
    max_revisions = max_response_revisions()

    def audited(name, node):
        def invoke(state: WorkflowState):
            attempt = state.get("revision_count", 0)
            audit_id = state.get("audit_id")
            try:
                if audit_id:
                    deps.audit.record_event(audit_id=audit_id, event="started", node=name, details={}, idempotency_key=f"{audit_id}:{name}:{attempt}:started")
                result = node(state)
                audit_id = state.get("audit_id") or result.get("audit_id")
                if audit_id:
                    if name in {"interpret", "analyze", "critique", "generate"}:
                        llm = deps.final_answer_llm if name == "generate" else deps.general_llm
                        usage = getattr(llm, "last_usage", None)
                        if usage:
                            deps.audit.record_event(audit_id=audit_id, event="llm_usage", node=name, details=usage, idempotency_key=f"{audit_id}:{name}:{attempt}:llm_usage")
                    details = {"error_code": result.get("error_code")}
                    if name == "validate":
                        violations = result.get("violations", [])
                        details.update({
                            "revision_count": result.get("revision_count", attempt),
                            "violation_count": len(violations),
                            "violations": " | ".join(violations),
                        })
                    deps.audit.record_event(audit_id=audit_id, event="completed", node=name, details=details, idempotency_key=f"{audit_id}:{name}:{attempt}:completed")
                return result
            except WorkflowServiceError as error:
                if audit_id:
                    try:
                        deps.audit.record_event(audit_id=audit_id, event="failed", node=name, details={"error_code": type(error).__name__}, idempotency_key=f"{audit_id}:{name}:{attempt}:failed")
                    except WorkflowServiceError:
                        pass
                return {"error_code": type(error).__name__, "final_answer": SAFE_LIMITATION}
        return invoke
    def initialize(state: WorkflowState):
        return {"audit_id": str(uuid.uuid4()), "revision_count": 0, "sources": [], "exams": []}

    def interpret(state: WorkflowState):
        result: InterpretationResult = deps.general_llm.interpret(question=state["question"])
        patient_id = result.candidate_patient_id if result.candidate_patient_id and result.candidate_patient_id.startswith("P-") else None
        condition = normalize_condition(result.candidate_condition, deps.condition_catalog)
        return {"patient_id": patient_id, "condition": condition, "error_code": "clarification" if not patient_id and not condition else None}

    def authorize(state: WorkflowState):
        patient_id = state.get("patient_id")
        return {"authorized": bool(patient_id and deps.authorization.is_patient_authorized(state["request_context"], patient_id))}

    def retrieve_record(state: WorkflowState):
        record = deps.repository.get_patient_record(state["patient_id"])
        if not record: return {"record": None, "error_code": "patient_not_found"}
        return {"record": record, "sources": _sources(record)}

    def retrieve_exams(state: WorkflowState):
        exams = deps.repository.get_pending_exams(state["patient_id"])
        return {"exams": exams, "sources": _sources(*state.get("sources", []), *(exam.source for exam in exams))}

    def retrieve_protocol(state: WorkflowState):
        protocol = deps.repository.get_protocol(state["condition"])
        return {"protocol": protocol, "sources": _sources(*state.get("sources", []), protocol) if protocol else state.get("sources", [])}

    def analyze(state: WorkflowState):
        context = "\n".join(source.snippet or source.title for source in state.get("sources", []))
        return {"analysis": deps.general_llm.analyze(question=state["question"], context=context, sources=state.get("sources", []))}

    def criticality(state: WorkflowState):
        return {"criticality": deps.criticality.evaluate(record=state.get("record"), exams=state.get("exams", []), protocol=state.get("protocol"))}

    def alert(state: WorkflowState):
        critical: CriticalityResult = state["criticality"]
        request = AlertRequest(audit_id=state["audit_id"], patient_id=state["patient_id"], rule_code=critical.rule_code or "UNKNOWN", rule_version=critical.rule_version, reason=critical.reason or "Criticidade sintética", idempotency_key=f"{state['audit_id']}:{critical.rule_code}")
        recorded = deps.alerts.record_simulated_alert(request)
        return {"alert_status": recorded.status}

    def generate(state: WorkflowState):
        context = "\n".join(f"[S{i + 1}] {source.snippet or source.title}" for i, source in enumerate(state.get("sources", [])))
        return {"draft": deps.final_answer_llm.generate(question=state["question"], context=context, sources=state.get("sources", []), revision_violations=state.get("violations", []), revision_attempt=state["revision_count"])}

    def enforce_critical_escalation(state: WorkflowState):
        critical = state.get("criticality", CriticalityResult(is_critical=False, rule_version="v1"))
        draft = state["draft"].strip()
        if not critical.is_critical or re.search(r"avaliação humana|procure.*(serviço|atendimento)|escalon", draft, re.IGNORECASE):
            return {"draft": draft}
        return {"draft": f"{draft}\n\n{CRITICAL_ESCALATION}"}

    def critique(state: WorkflowState):
        return {"critique": deps.general_llm.critique(question=state["question"], answer=state["draft"], sources=state.get("sources", []), has_individual_context=bool(state.get("record")), is_critical=state.get("criticality", CriticalityResult(is_critical=False, rule_version="v1")).is_critical)}

    def validate(state: WorkflowState):
        validation = deps.validator.validate(answer=state.get("draft", state.get("final_answer", "")), sources=state.get("sources", []), has_individual_context=bool(state.get("record")), is_critical=state.get("criticality", CriticalityResult(is_critical=False, rule_version="v1")).is_critical, critique=state.get("critique", CritiqueResult()))
        if validation.approved: return {"final_answer": state["draft"], "violations": []}
        if validation.requires_revision and state["revision_count"] < max_revisions:
            return {"violations": validation.violations, "revision_count": state["revision_count"] + 1}
        return {"final_answer": validation.safe_message or SAFE_LIMITATION, "violations": validation.violations}

    def limitation(state: WorkflowState):
        return {"final_answer": SAFE_LIMITATION}

    def route_after_interpret(state: WorkflowState):
        if state.get("error_code") and state["error_code"] != "clarification": return "limitation"
        if state.get("error_code") == "clarification": return "limitation"
        return "authorize" if state.get("patient_id") else "protocol"
    def route_after_authorize(state: WorkflowState): return "record" if state.get("authorized") and not state.get("error_code") else "limitation"
    def route_after_record(state: WorkflowState): return "limitation" if state.get("error_code") else "exams"
    def route_after_exams(state: WorkflowState): return "limitation" if state.get("error_code") else ("protocol" if state.get("condition") else "analyze")
    def route_after_protocol(state: WorkflowState): return "limitation" if state.get("error_code") else "analyze"
    def route_after_analyze(state: WorkflowState): return "limitation" if state.get("error_code") else "criticality"
    def route_after_criticality(state: WorkflowState):
        if state.get("error_code"): return "limitation"
        critical = state["criticality"].is_critical
        if critical and state.get("patient_id"): return "alert"
        if critical: return "limitation"
        return "generate"
    def route_after_validate(state: WorkflowState):
        return "generate" if state.get("revision_count", 0) <= max_revisions and not state.get("final_answer") else END
    def route_after_alert(state: WorkflowState): return "limitation" if state.get("error_code") else "generate"
    def route_after_generate(state: WorkflowState): return "limitation" if state.get("error_code") else "enforce_critical_escalation"
    def route_after_enforce_critical_escalation(state: WorkflowState): return "limitation" if state.get("error_code") else "critique"
    def route_after_critique(state: WorkflowState): return "limitation" if state.get("error_code") else "validate"

    graph = StateGraph(WorkflowState)
    for name, node in {"initialize": initialize, "interpret": interpret, "authorize": authorize, "record": retrieve_record, "exams": retrieve_exams, "protocol": retrieve_protocol, "analyze": analyze, "criticality": criticality, "alert": alert, "generate": generate, "enforce_critical_escalation": enforce_critical_escalation, "critique": critique, "validate": validate, "limitation": limitation}.items(): graph.add_node(name, audited(name, node))
    graph.add_edge(START, "initialize"); graph.add_edge("initialize", "interpret")
    graph.add_conditional_edges("interpret", route_after_interpret, {"authorize": "authorize", "protocol": "protocol", "limitation": "limitation"})
    graph.add_conditional_edges("authorize", route_after_authorize, {"record": "record", "limitation": "limitation"})
    graph.add_conditional_edges("record", route_after_record, {"exams": "exams", "limitation": "limitation"})
    graph.add_conditional_edges("exams", route_after_exams, {"protocol": "protocol", "analyze": "analyze"})
    graph.add_conditional_edges("protocol", route_after_protocol, {"analyze": "analyze", "limitation": "limitation"})
    graph.add_conditional_edges("analyze", route_after_analyze, {"criticality": "criticality", "limitation": "limitation"})
    graph.add_conditional_edges("criticality", route_after_criticality, {"alert": "alert", "generate": "generate", "limitation": "limitation"})
    graph.add_conditional_edges("alert", route_after_alert, {"generate": "generate", "limitation": "limitation"})
    graph.add_conditional_edges("generate", route_after_generate, {"enforce_critical_escalation": "enforce_critical_escalation", "limitation": "limitation"})
    graph.add_conditional_edges("enforce_critical_escalation", route_after_enforce_critical_escalation, {"critique": "critique", "limitation": "limitation"})
    graph.add_conditional_edges("critique", route_after_critique, {"validate": "validate", "limitation": "limitation"})
    graph.add_conditional_edges("validate", route_after_validate, {"generate": "generate", END: END})
    graph.add_edge("limitation", END)
    return graph.compile()
