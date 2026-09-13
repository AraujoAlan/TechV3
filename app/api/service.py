from __future__ import annotations

import uuid

from app.api.schemas import AlertOut, ChatResponse, SourceOut
from app.contracts.models import RequestContext, Source
from app.graph.workflow import SAFE_LIMITATION, WorkflowDependencies, build_workflow
from app.runtime import prepare_fake_interpretation


def run_chat(
    *,
    deps: WorkflowDependencies,
    question: str,
    conversation_id: str | None,
    requester_id: str,
    authorized_patient_ids: frozenset[str],
) -> ChatResponse:
    prepare_fake_interpretation(deps, question)
    context = RequestContext(
        conversation_id=conversation_id or str(uuid.uuid4()),
        requester_id=requester_id,
        authorized_patient_ids=authorized_patient_ids,
    )
    state = build_workflow(deps).invoke({"question": question, "request_context": context})
    return map_public_response(state)


def map_public_response(state: dict) -> ChatResponse:
    answer = state.get("final_answer") or SAFE_LIMITATION
    sources = [_source_out(source) for source in state.get("sources", [])]
    alert_status = state.get("alert_status")
    alert = AlertOut(status="simulated_recorded") if alert_status == "simulated_recorded" else None
    limited = answer.strip() == SAFE_LIMITATION or bool(state.get("error_code"))
    return ChatResponse(
        audit_id=state.get("audit_id") or str(uuid.uuid4()),
        outcome="limited" if limited else "completed",
        answer=answer,
        sources=sources,
        alert=alert,
    )


def _source_out(source: Source | dict) -> SourceOut:
    if isinstance(source, Source):
        return SourceOut(id=source.id, title=source.title, snippet=source.snippet, kind=source.kind)
    return SourceOut(
        id=source["id"],
        title=source["title"],
        snippet=source.get("snippet"),
        kind=source["kind"],
    )
