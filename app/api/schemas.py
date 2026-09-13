from typing import Literal

from pydantic import BaseModel, Field


MAX_QUESTION_LENGTH = 2000


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    conversation_id: str | None = Field(default=None, max_length=128)


class SourceOut(BaseModel):
    id: str
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"]


class AlertOut(BaseModel):
    status: Literal["simulated_recorded"]


class ChatResponse(BaseModel):
    audit_id: str
    outcome: Literal["completed", "limited"]
    answer: str
    sources: list[SourceOut] = Field(default_factory=list)
    alert: AlertOut | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    mode: Literal["demo"] = "demo"
