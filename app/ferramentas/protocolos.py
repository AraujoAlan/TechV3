"""Tool de consulta aos protocolos internos do hospital.

Vem do `consultar_protocolo` do protótipo em `main.py`. Mudaram três coisas: os
protocolos saíram do código para `dados_hospital/protocolos.json`, o conteúdo
passou a ser de maternidade (o escopo do modelo fine-tunado) e a busca passou a
ser **só por código CID-10**.

A busca por nome foi tentada e descartada. Ela errava no que tinha de mais
comum — "hemorragia pos parto" não casava com "hemorragia pós-parto" por causa
de um hífen — e cada correção empilhava mais heurística de texto. O CID resolve
melhor por dois motivos:

- o `diagnostico_principal` do prontuário **já é um código CID-10**, então o
  agente vai do paciente ao protocolo sem intermediário nenhum;
- quando o médico pergunta pelo nome ("qual o protocolo de pré-eclâmpsia?"),
  quem traduz para O14 é o roteador, que é um modelo de linguagem e sabe fazer
  isso. `listar_protocolos` dá a ele o mapa.

Cada camada faz o que sabe: o modelo interpreta, o código consulta de forma
determinística. E o resultado é auditável — dá para conferir por que aquele
protocolo foi devolvido.

Os protocolos são fictícios e escritos para este trabalho. O aviso viaja junto
do texto devolvido, não só no arquivo — assim ele chega ao redator.
"""

import json
import re
from functools import lru_cache

from langchain_core.tools import tool

from app import config

CAMINHO_PROTOCOLOS = config.DIRETORIO_PUBLICADO / "protocolos.json"

# Código CID-10 como aparece em `diagnostico_principal`: letra, dois dígitos e
# eventualmente a subcategoria (O14, O140, P599). O casamento é pelos três
# primeiros caracteres, que é o nível em que os protocolos são escritos.
PADRAO_CID = re.compile(r"^[A-Z]\d{2}")


@lru_cache(maxsize=1)
def carregar_protocolos() -> dict:
    with CAMINHO_PROTOCOLOS.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _formatar(protocolo: dict, aviso: str) -> str:
    condutas = "\n".join(f"{i}. {c}" for i, c in enumerate(protocolo["condutas"], 1))
    return (
        f"{protocolo['id']} — {protocolo['titulo']} (CID {protocolo['cid']})\n"
        f"{protocolo['resumo']}\n\n"
        f"CONDUTAS PREVISTAS\n{condutas}\n\n"
        f"QUANDO ACIONAR A EQUIPE: {protocolo['acionar_equipe']}\n\n"
        f"[{aviso}]"
    )


def _indice() -> str:
    """Condição e faixa de CID de cada protocolo, uma por linha."""
    dados = carregar_protocolos()
    return "\n".join(
        f"- {p['condicao']} — CID {p['cid']} ({', '.join(p['cid_prefixos'])})"
        for p in dados["protocolos"]
    )


@tool(response_format="content_and_artifact")
def consultar_protocolo(cid: str) -> tuple[str, dict]:
    """Consulta o protocolo interno do hospital pelo código CID-10.

    A busca é só por código. Se o médico perguntou pelo nome da condição,
    converta você mesmo para o CID correspondente antes de chamar — ou use
    `listar_protocolos` para ver o que existe.

    Args:
        cid: código CID-10, como aparece em `diagnostico_principal` no
            prontuário. Ex.: "O14", "O140", "P599".
    """
    dados = carregar_protocolos()
    entrada = cid.strip().upper()

    if not PADRAO_CID.match(entrada):
        return (
            f"'{cid}' não é um código CID-10. Esta ferramenta busca só por código "
            f"(formato letra + dois dígitos, como O14 ou P59).\n\n"
            f"Protocolos disponíveis:\n{_indice()}"
        ), {
            "fonte": {
                "id": "protocolo-entrada-invalida",
                "title": f"'{cid}' não é um código CID-10",
                "snippet": "A consulta a protocolo é feita por código.",
                "kind": "protocolo",
            }
        }

    prefixo = entrada[:3]
    protocolo = next(
        (p for p in dados["protocolos"] if prefixo in p["cid_prefixos"]), None
    )

    if protocolo is None:
        texto = (
            f"O hospital não tem protocolo interno para o CID {entrada}.\n\n"
            f"Protocolos disponíveis:\n{_indice()}\n\n"
            "Diga isso ao médico em vez de responder como se houvesse protocolo."
        )
        return texto, {
            "fonte": {
                "id": "protocolo-inexistente",
                "title": f"Sem protocolo interno para o CID {entrada}",
                "snippet": "O código consultado não está coberto pelos protocolos.",
                "kind": "protocolo",
            }
        }

    return _formatar(protocolo, dados["aviso"]), {
        "fonte": {
            "id": protocolo["id"],
            "title": f"{protocolo['id']} — {protocolo['titulo']}",
            "snippet": f"{protocolo['resumo']} (consultado pelo CID {entrada})",
            "kind": "protocolo",
        }
    }


@tool(response_format="content_and_artifact")
def listar_protocolos() -> tuple[str, dict]:
    """Lista os protocolos internos do hospital, com a faixa de CID de cada um.

    Use para descobrir qual código passar a `consultar_protocolo` quando o
    médico perguntou pelo nome da condição.
    """
    dados = carregar_protocolos()
    return f"Protocolos internos disponíveis:\n{_indice()}", {
        "fonte": {
            "id": "protocolos-indice",
            "title": "Índice de protocolos internos",
            "snippet": f"{len(dados['protocolos'])} protocolos, versão {dados['versao']}",
            "kind": "protocolo",
        }
    }


FERRAMENTAS_PROTOCOLO = [consultar_protocolo, listar_protocolos]
