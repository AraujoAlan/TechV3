"""O agente do assistente médico.

É um `create_agent` só, com dois modelos dentro dele:

    médico pergunta
      → GLM decide e chama ferramentas (banco, protocolos, alertas)
      → GLM decide que já tem o suficiente
      → o modelo fine-tunado escreve a resposta
      → médico lê

A troca acontece no middleware `escrever_com_modelo_finetunado`. Ele deixa o
agente rodar normalmente e observa cada resposta do modelo: enquanto vierem tool
calls, o GLM segue no comando; quando vier uma resposta sem tool call, a rota
acabou — e essa fala é refeita com o modelo fine-tunado, com o system prompt do
treino e sem ferramenta nenhuma na mão.

Por que dois modelos, e não um. O GLM sabe montar tool call com argumento certo,
que é o que o loop exige; o nosso modelo foi ajustado em pares pergunta-resposta
clínicos, sem um único exemplo de tool calling. Cada um faz o que treinou.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware, wrap_model_call
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app import config
from app.ferramentas.alertas import FERRAMENTAS_ALERTA
from app.ferramentas.protocolos import FERRAMENTAS_PROTOCOLO
from app.ferramentas.sql import FERRAMENTAS_SQL
from app.grafo.prompts import (
    SYSTEM_ASSISTENTE,
    SYSTEM_ROTEADOR,
    montar_pergunta_com_contexto,
)
from app.llm.redator import criar_redator
from app.llm.roteador import criar_roteador

FERRAMENTAS = [*FERRAMENTAS_SQL, *FERRAMENTAS_PROTOCOLO, *FERRAMENTAS_ALERTA]


def montar_conversa_do_redator(mensagens: list) -> list:
    """Reconstrói a conversa como o modelo fine-tunado espera vê-la.

    O que chega aqui é o rascunho do roteador: pergunta, decisões de tool call e
    resultados de ferramenta, tudo misturado. O modelo fine-tunado nunca viu isso
    no treino — ele viu system, pergunta, resposta. Então a conversa é remontada
    nesse formato, com o que as ferramentas trouxeram anexado à pergunta do turno.
    """
    corte = max(
        (i for i, m in enumerate(mensagens) if isinstance(m, HumanMessage)),
        default=0,
    )
    pergunta = mensagens[corte].content if mensagens else ""

    # Histórico: só as falas de verdade. Tool call e resultado de ferramenta de
    # turnos passados não entram — são o caderno de rascunho do roteador.
    historico = [
        m
        for m in mensagens[:corte]
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and m.content and not m.tool_calls)
    ]

    resultados = [m for m in mensagens[corte:] if isinstance(m, ToolMessage)]
    contexto = "\n\n".join(
        f"[{m.name}]\n{m.content}" for m in resultados if str(m.content).strip()
    )

    return [
        SystemMessage(SYSTEM_ASSISTENTE),
        *historico,
        HumanMessage(montar_pergunta_com_contexto(pergunta, contexto)),
    ]


@wrap_model_call
async def escrever_com_modelo_finetunado(request, handler):
    """Passa a caneta para o modelo fine-tunado quando a rota termina."""
    resposta = await handler(request)

    ultima = resposta.result[-1]
    if getattr(ultima, "tool_calls", None):
        return resposta  # ainda consultando: o GLM continua

    pedido = request.override(
        model=criar_redator(),
        tools=[],  # a resposta final não chama ferramenta
        system_message=SystemMessage(SYSTEM_ASSISTENTE),
        messages=montar_conversa_do_redator(request.messages),
    )
    return await handler(pedido)


def construir_agente():
    """Monta o agente do assistente."""
    return create_agent(
        model=criar_roteador(),
        tools=FERRAMENTAS,
        system_prompt=SYSTEM_ROTEADOR,
        middleware=[
            # O teto de chamadas não é economia: é o que impede o agente de
            # entrar em laço de consulta e deixar o médico esperando. Com
            # `continue`, as chamadas excedentes são bloqueadas mas o turno segue
            # até a resposta — melhor que estourar erro na cara de quem perguntou.
            ToolCallLimitMiddleware(
                run_limit=config.ROTEADOR_MAX_PASSOS, exit_behavior="continue"
            ),
            escrever_com_modelo_finetunado,
        ],
        name="assistente",
    )
