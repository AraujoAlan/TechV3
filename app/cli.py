import argparse
import sqlite3
import re

from dotenv import load_dotenv

from app.contracts.models import RequestContext
from app.graph.workflow import WorkflowDependencies, build_workflow
from app.llm.factory import OpenAIGeneralLLM, QwenLoraFinalAnswerLLM
from app.llm.fakes import FakeFinalAnswerLLM, FakeGeneralLLM
from app.services.alert_service import SqliteAlertService
from app.services.audit_logger import SqliteAuditLogger
from app.services.authorization import DemoAuthorizationService
from app.services.criticality import MaternalInfantCriticalityService
from app.services.medical_repository import MedicalRepositorySqlite
from app.services.safety_validator import DeterministicSafetyValidator


def build_dependencies(database: str, use_fakes: bool) -> WorkflowDependencies:
    repository = MedicalRepositorySqlite.open(database)
    repository.initialize()
    connection = repository.connection
    general = FakeGeneralLLM() if use_fakes else OpenAIGeneralLLM()
    final = FakeFinalAnswerLLM() if use_fakes else QwenLoraFinalAnswerLLM()
    return WorkflowDependencies(DemoAuthorizationService(), repository, MaternalInfantCriticalityService(), SqliteAlertService(connection), SqliteAuditLogger(connection), general, final, DeterministicSafetyValidator())


def main() -> int:
    # Variáveis exportadas no shell prevalecem sobre o arquivo local.
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description="Demo sintética do workflow LangGraph")
    parser.add_argument("question", nargs="?", default="Quais sinais exigem atenção na hipertensão gestacional?")
    parser.add_argument("--authorized-patient", action="append", default=[])
    parser.add_argument("--database", default="clinical_demo.db")
    parser.add_argument("--fake", action="store_true", help="Usa LLMs determinísticas; exclusivo para desenvolvimento e testes.")
    parser.add_argument("--smoke-general-llm", action="store_true")
    parser.add_argument("--smoke-final-answer-llm", action="store_true")
    args = parser.parse_args()
    if args.smoke_general_llm:
        print(OpenAIGeneralLLM().smoke_test()); return 0
    if args.smoke_final_answer_llm:
        print(QwenLoraFinalAnswerLLM().smoke_test()); return 0
    deps = build_dependencies(args.database, args.fake)
    if args.fake:
        from app.contracts.models import InterpretationResult
        deps.general_llm.interpretation = InterpretationResult(
            candidate_patient_id=re.search(r"P-\d+", args.question).group(0) if re.search(r"P-\d+", args.question) else None,
            candidate_condition="hipertensao-gestacional" if "hipertens" in args.question.lower() else None,
            requires_clarification=not ("P-" in args.question or "hipertens" in args.question.lower()),
        )
    graph = build_workflow(deps)
    context = RequestContext(conversation_id="demo-cli", requester_id="demo-cli", authorized_patient_ids=frozenset(args.authorized_patient))
    state = graph.invoke({"question": args.question, "request_context": context})
    print(state["final_answer"])
    for index, source in enumerate(state.get("sources", []), start=1): print(f"[S{index}] {source.id} — {source.title}")
    if state.get("alert_status"): print("Alerta simulado registrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
