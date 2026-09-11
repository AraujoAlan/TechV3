"""Traduz o stream do agente nos seis eventos do contrato SSE.

O agente emite o vocabulário do LangGraph: atualizações de nó e pedaços de
mensagem. O frontend espera `token`, `tool_start`, `tool_end`, `sources`, `done`
e `error`. Este módulo é a tradução entre os dois, e é o único lugar que conhece
os dois lados.

Duas regras do contrato são mantidas aqui, não no agente:

- todo `tool_start` tem um `tool_end` com o mesmo `id` — o que sai de graça
  usando o `tool_call_id`, que é a correlação que o próprio LangChain já faz;
- `done` é sempre o último evento, mesmo quando o turno termina em erro.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.llm.redator import ETIQUETA_REDATOR, FiltroPensamento
from app.seguranca import limites
from app.seguranca.auditoria import RegistroDoTurno


def evento_sse(dado: dict) -> str:
    """Formata um evento no formato que o `data:` do SSE exige."""
    return f"data: {json.dumps(dado, ensure_ascii=False)}\n\n"


def _mensagens_do_update(dado: Any) -> list:
    """Extrai as mensagens de uma atualização de nó, seja qual for o nó."""
    mensagens = []
    for atualizacao in (dado or {}).values():
        if isinstance(atualizacao, dict):
            mensagens.extend(atualizacao.get("messages") or [])
    return mensagens


async def transmitir(
    agente,
    mensagens_de_entrada: list,
    conversa_id: str,
    mensagem_id: str,
) -> AsyncIterator[str]:
    """Roda um turno e vai emitindo os eventos conforme eles acontecem."""
    pergunta = next(
        (m.content for m in reversed(mensagens_de_entrada) if isinstance(m, HumanMessage)),
        "",
    )

    filtro = FiltroPensamento()
    fontes: dict[str, dict] = {}
    partes_da_resposta: list[str] = []

    with RegistroDoTurno(conversa_id, pergunta) as registro:
        try:
            async for modo, dado in agente.astream(
                {"messages": mensagens_de_entrada},
                stream_mode=["updates", "messages"],
            ):
                if modo == "messages":
                    pedaco, metadados = dado
                    if ETIQUETA_REDATOR not in (metadados.get("tags") or []):
                        # Tokens do roteador e conteúdo de ferramenta também
                        # passam por aqui. Só o redator fala com o médico.
                        continue
                    texto = filtro.processar(str(pedaco.content))
                    if texto:
                        partes_da_resposta.append(texto)
                        yield evento_sse({"type": "token", "content": texto})
                    continue

                for mensagem in _mensagens_do_update(dado):
                    if isinstance(mensagem, AIMessage) and mensagem.tool_calls:
                        for chamada in mensagem.tool_calls:
                            yield evento_sse(
                                {
                                    "type": "tool_start",
                                    "id": chamada["id"],
                                    "name": chamada["name"],
                                    "input": chamada["args"],
                                }
                            )
                    elif isinstance(mensagem, ToolMessage):
                        saida = str(mensagem.content)
                        yield evento_sse(
                            {
                                "type": "tool_end",
                                "id": mensagem.tool_call_id,
                                "output": saida,
                            }
                        )
                        registro.registrar_ferramenta(
                            mensagem.name or "?", {}, saida
                        )
                        fonte = (mensagem.artifact or {}).get("fonte")
                        if fonte:
                            fontes.setdefault(fonte["id"], fonte)

            resto = filtro.finalizar()
            if resto:
                partes_da_resposta.append(resto)
                yield evento_sse({"type": "token", "content": resto})

            resposta = "".join(partes_da_resposta)
            registro.resposta = resposta
            registro.fontes = list(fontes.values())
            registro.alertas = limites.verificar(
                resposta, [f["nome"] for f in registro.ferramentas]
            )

            if fontes:
                yield evento_sse(
                    {"type": "sources", "sources": list(fontes.values())}
                )

        except Exception as erro:  # noqa: BLE001 — a falha vira mensagem, não stack
            registro.erro = f"{type(erro).__name__}: {erro}"
            yield evento_sse(
                {
                    "type": "error",
                    "message": _mensagem_de_erro(erro),
                }
            )

        # Fora do try de propósito: `done` fecha o turno em qualquer caminho, que
        # é o que o frontend espera para sair do estado de digitando.
        yield evento_sse(
            {
                "type": "done",
                "messageId": mensagem_id,
                "conversationId": conversa_id,
            }
        )


def _mensagem_de_erro(erro: Exception) -> str:
    """Texto para o médico ler — não stack trace, como pede o contrato."""
    nome = type(erro).__name__
    if "Connection" in nome or "APIConnection" in nome:
        return (
            "Não consegui falar com o modelo. Verifique se o serviço do modelo "
            "está no ar e tente de novo."
        )
    if "Timeout" in nome:
        return "O modelo demorou demais para responder. Tente de novo."
    return "Houve uma falha ao processar sua pergunta. Tente de novo."
