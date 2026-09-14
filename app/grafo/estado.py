"""O estado que atravessa o grafo do turno.

Um `TypedDict` com `total=False`: cada nó devolve só as chaves que mudou, e o
LangGraph funde o resultado no estado.

Duas chaves não são "mais um campo" e merecem explicação.

`messages` existe para a camada de transmissão tanto quanto para o grafo. O
`app/api/transmissao.py` lê as mensagens de cada atualização de nó para emitir
`tool_start` e `tool_end` ao frontend — é dali que sai a trilha de ferramentas
que o médico vê. Um estado sem `messages` compilaria e rodaria, e a interface
ficaria muda durante as consultas. É também o formato que o agente roteador
espera, o que permite plugá-lo como subgrafo sem tradução.

`fontes` acumula em vez de substituir. As fontes nascem espalhadas — uma por
resultado de ferramenta — e o evento `sources` do contrato é único, no fim do
turno. A deduplicação por `id` é necessária porque o roteador repete consulta:
perguntar duas vezes pelo mesmo paciente não deve citar o prontuário duas vezes.
"""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from app.seguranca.criticidade import Criticidade


def juntar_fontes(atual: list[dict] | None, novas: list[dict] | None) -> list[dict]:
    """Acumula fontes preservando a ordem de descoberta, sem repetir `id`."""
    resultado = list(atual or [])
    vistos = {fonte["id"] for fonte in resultado}

    for fonte in novas or []:
        if fonte["id"] not in vistos:
            resultado.append(fonte)
            vistos.add(fonte["id"])

    return resultado


class EstadoDoTurno(TypedDict, total=False):
    """O que o grafo sabe sobre o turno em andamento."""

    # --- entrada -------------------------------------------------------------
    messages: Annotated[list, add_messages]
    pergunta: str

    # --- identificação do turno na auditoria ---------------------------------
    turno_id: str

    # --- o que a pergunta e a recuperação trouxeram --------------------------
    id_paciente: str | None
    fontes: Annotated[list[dict], juntar_fontes]
    ferramentas_usadas: list[str]

    # --- avaliação determinística --------------------------------------------
    criticidade: Criticidade
    alerta_id: str | None

    # --- redação e revisão ----------------------------------------------------
    rascunho: str
    resposta: str
    violacoes: list[str]
    # Quantas vezes a resposta já foi refeita. Zero no primeiro passe.
    revisao: int

    # --- falha ----------------------------------------------------------------
    # Preenchido quando um serviço falha. Todo roteamento consulta esta chave
    # antes de seguir, e ela desvia o fluxo para o nó `limitacao`.
    codigo_erro: str | None
