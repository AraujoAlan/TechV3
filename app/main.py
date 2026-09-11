"""Entrada da API do assistente médico.

Serve dois caminhos e o frontend:

    POST /api/chat     conversa, em SSE
    GET  /api/health   sonda de vida
    /                  o build do Vite, quando existe

O frontend e a API saem da mesma origem de propósito — é o que
`frontend/CONTRATO.md` assume, e é o que dispensa CORS.

    uvicorn app.main:aplicacao --reload
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage

from app import config
from app.api.esquemas import PedidoDeChat
from app.api.transmissao import transmitir
from app.grafo.construcao import construir_agente
from app.hospital import banco, montagem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("assistente")

# Cabeçalhos que o streaming exige. O `X-Accel-Buffering` só importa se houver
# nginx na frente: sem ele o proxy bufferiza e o efeito de digitação morre.
CABECALHOS_SSE = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    montagem.montar()
    aplicacao.state.agente = construir_agente()
    logger.info(
        "assistente pronto | roteador=%s | redator=%s @ %s",
        config.ROTEADOR_MODELO,
        config.REDATOR_MODELO,
        config.REDATOR_BASE_URL,
    )
    yield
    banco.fechar_banco()


aplicacao = FastAPI(title="Assistente Médico Virtual", lifespan=ciclo_de_vida)


@aplicacao.get("/api/health")
async def saude() -> dict:
    return {"status": "ok"}


@aplicacao.post("/api/chat")
async def conversar(pedido: PedidoDeChat) -> StreamingResponse:
    conversa_id = pedido.conversationId or f"conv_{uuid.uuid4().hex[:8]}"
    mensagem_id = f"msg_{uuid.uuid4().hex[:8]}"

    # O frontend manda o histórico inteiro a cada turno, então o agente é
    # stateless: não há checkpointer, e recarregar a página começa do zero.
    mensagens = [
        HumanMessage(m.content) if m.role == "user" else AIMessage(m.content)
        for m in pedido.messages
    ]

    return StreamingResponse(
        transmitir(aplicacao.state.agente, mensagens, conversa_id, mensagem_id),
        media_type="text/event-stream",
        headers=CABECALHOS_SSE,
    )


# Por último: a rota "/" captura tudo que não casou acima, então precisa vir
# depois das rotas de API.
if config.DIRETORIO_FRONTEND.is_dir():
    aplicacao.mount(
        "/",
        StaticFiles(directory=config.DIRETORIO_FRONTEND, html=True),
        name="frontend",
    )
else:
    logger.warning(
        "frontend não encontrado em %s — a API sobe, mas só responde /api/*. "
        "Rode `npm run build` em frontend/ para servir a interface junto.",
        config.DIRETORIO_FRONTEND,
    )
