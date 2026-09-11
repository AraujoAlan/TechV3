"""Os tipos da API, espelhando `frontend/src/api/types.ts`.

Se mudar aqui, mude lá — e no `frontend/CONTRATO.md`, que é o documento que o
time usou para escrever a interface antes de existir backend.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Mensagem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PedidoDeChat(BaseModel):
    """Corpo do `POST /api/chat`."""

    messages: list[Mensagem] = Field(min_length=1)
    conversationId: str | None = None  # noqa: N815 — o nome vem do contrato


class Fonte(BaseModel):
    """Origem citada na resposta, para explainability."""

    id: str
    title: str
    snippet: str | None = None
    kind: Literal["protocolo", "prontuario", "exame", "documento"] | None = None
