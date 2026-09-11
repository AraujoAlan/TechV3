"""Tool de alerta para a equipe médica.

Vem do `registrar_alerta_equipe` do protótipo em `main.py`. A mudança é que o
alerta deixou de ser um `print` e passou a ser uma linha em
`logs/alertas.jsonl` — um alerta que só aparece no terminal de quem rodou o
processo não é alerta.

Continua sendo uma simulação: num hospital real isso chamaria o sistema de
notificação de plantão. O que o trabalho demonstra é o gatilho e o rastro.
"""

import json
import threading
from datetime import datetime, timezone

from langchain_core.tools import tool

from app import config

CAMINHO_ALERTAS = config.CAMINHO_LOG.parent / "alertas.jsonl"

_lock = threading.Lock()

PRIORIDADES = ("rotina", "urgente", "emergencia")


@tool(response_format="content_and_artifact")
def registrar_alerta_equipe(
    id_paciente: str, mensagem: str, prioridade: str = "urgente"
) -> tuple[str, dict]:
    """Registra um alerta para a equipe médica de plantão sobre um paciente.

    Use quando a consulta revelar uma situação que a equipe precisa saber agora
    — não para resumir o atendimento. O alerta não substitui contato direto em
    emergência.

    Args:
        id_paciente: identificador do paciente (ex.: PAC00000001).
        mensagem: o que a equipe precisa saber, em uma frase.
        prioridade: rotina, urgente ou emergencia.
    """
    prioridade = prioridade.strip().lower()
    if prioridade not in PRIORIDADES:
        prioridade = "urgente"

    momento = datetime.now(timezone.utc)
    identificador = f"ALERTA-{momento.strftime('%Y%m%d%H%M%S')}-{id_paciente}"

    registro = {
        "id": identificador,
        "quando": momento.isoformat(),
        "id_paciente": id_paciente,
        "prioridade": prioridade,
        "mensagem": mensagem,
        "origem": "assistente-virtual",
        # O alerta é sugestão do assistente até alguém da equipe confirmar.
        # Registrar isso aqui é o que impede que ele seja lido depois como
        # decisão clínica tomada.
        "validado_por_humano": False,
    }

    CAMINHO_ALERTAS.parent.mkdir(parents=True, exist_ok=True)
    with _lock, CAMINHO_ALERTAS.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")

    texto = (
        f"Alerta {identificador} registrado ({prioridade}) para o paciente "
        f"{id_paciente}. Pendente de validação por um profissional da equipe."
    )
    return texto, {
        "fonte": {
            "id": identificador,
            "title": f"Alerta {prioridade} — paciente {id_paciente}",
            "snippet": mensagem,
            "kind": "documento",
        }
    }


FERRAMENTAS_ALERTA = [registrar_alerta_equipe]
