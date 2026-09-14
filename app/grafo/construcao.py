"""Montagem do assistente: o agente que consulta, dentro do grafo que controla.

São dois modelos e duas responsabilidades:

    médico pergunta
      → GLM decide e chama ferramentas (banco, protocolos, alertas)
      → o grafo avalia criticidade e, se for o caso, alerta a equipe
      → o modelo fine-tunado escreve a resposta
      → o grafo confere a resposta antes de entregá-la
      → médico lê

Por que dois modelos, e não um. O GLM sabe montar tool call com argumento certo,
que é o que o laço de consulta exige; o nosso modelo foi ajustado em pares
pergunta-resposta clínicos, sem um único exemplo de tool calling. Cada um faz o
que treinou.

Por que um grafo em volta, e não só o agente. O agente decide sozinho quando
parar de consultar e o que responder — e isso basta para conversar, mas não para
sustentar as garantias que a fase pede. Criticidade avaliada por regra,
escalonamento obrigatório e resposta conferida antes de sair não podem depender
de o modelo ter lembrado: são nós do grafo, executados sempre, e cada passagem
deixa linha na auditoria.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware

from app import config
from app.ferramentas.alertas import FERRAMENTAS_ALERTA
from app.ferramentas.protocolos import FERRAMENTAS_PROTOCOLO
from app.ferramentas.sql import FERRAMENTAS_SQL
from app.grafo.fluxo import montar_grafo
from app.grafo.prompts import SYSTEM_ROTEADOR
from app.llm.roteador import criar_roteador

FERRAMENTAS = [*FERRAMENTAS_SQL, *FERRAMENTAS_PROTOCOLO, *FERRAMENTAS_ALERTA]


def construir_roteador():
    """O agente que levanta os dados, sem escrever a resposta final.

    A redação saiu daqui: ela é um nó do grafo, depois da avaliação de
    criticidade. Enquanto o redator era um middleware deste agente, ele
    escrevia antes de qualquer verificação — e não havia onde encaixar o
    escalonamento obrigatório sem reescrever texto já entregue.
    """
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
        ],
        name="roteador",
    )


def construir_agente():
    """Monta o assistente inteiro, pronto para receber um turno."""
    return montar_grafo(construir_roteador())
