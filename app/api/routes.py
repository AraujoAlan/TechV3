from __future__ import annotations

import asyncio
import threading
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_invoke_lock,
    get_workflow_deps,
)
from app.api.schemas import ChatRequest, ChatResponse, HealthResponse
from app.api.service import run_chat
from app.graph.workflow import WorkflowDependencies

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    deps: Annotated[WorkflowDependencies, Depends(get_workflow_deps)],
    invoke_lock: Annotated[threading.Lock, Depends(get_invoke_lock)],
) -> ChatResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="A pergunta não pode ser vazia.")

    def _invoke() -> ChatResponse:
        with invoke_lock:
            return run_chat(
                deps=deps,
                question=question,
                conversation_id=body.conversation_id,
                requester_id=principal.requester_id,
                authorized_patient_ids=principal.authorized_patient_ids,
            )

    try:
        return await asyncio.to_thread(_invoke)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Não foi possível concluir a solicitação. Tente novamente.",
        ) from None
