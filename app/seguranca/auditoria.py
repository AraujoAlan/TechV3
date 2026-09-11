"""Registro de auditoria das conversas.

A fase pede "logging detalhado para rastreamento e auditoria". Num sistema que
apoia decisão clínica isso não é burocracia: se uma resposta induzir a uma
conduta errada, alguém precisa reconstruir depois o que o assistente consultou
e o que ele respondeu.

Cada turno vira uma linha JSON em `logs/auditoria.jsonl`: pergunta, tools
chamadas com seus argumentos, SQL executado, fontes citadas, resposta, latência
e alertas de limite. JSONL porque é o formato que dá para inspecionar com
`jq`/`duckdb` sem subir infraestrutura nenhuma.

Não há dado pessoal a proteger aqui — o banco é sintético —, mas o formato já é
o que se usaria com dado real, e é o que o relatório descreve.
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone

from app import config

_lock = threading.Lock()

logger = logging.getLogger("assistente")


class RegistroDoTurno:
    """Acumula o que aconteceu num turno e grava uma linha ao final.

    Use como context manager: a linha é gravada mesmo quando o turno termina em
    erro ou é cancelado pelo médico, que são justamente os casos que a auditoria
    precisa registrar.
    """

    def __init__(self, conversa_id: str, pergunta: str):
        self.conversa_id = conversa_id
        self.pergunta = pergunta
        self.ferramentas: list[dict] = []
        self.fontes: list[dict] = []
        self.resposta = ""
        self.alertas: list[str] = []
        self.erro: str | None = None
        self._inicio = time.monotonic()

    def registrar_ferramenta(self, nome: str, argumentos: dict, saida: str) -> None:
        self.ferramentas.append(
            {
                "nome": nome,
                "argumentos": argumentos,
                # A saída inteira pode ser um prontuário de 1,2 mil caracteres.
                # O suficiente para auditar é saber o que voltou e o tamanho.
                "saida_inicio": saida[:400],
                "saida_chars": len(saida),
            }
        )

    def __enter__(self) -> "RegistroDoTurno":
        return self

    def __exit__(self, tipo_erro, erro, _traceback) -> bool:
        if erro is not None:
            self.erro = f"{tipo_erro.__name__}: {erro}"
        self.gravar()
        return False  # não engole a exceção

    def gravar(self) -> None:
        linha = {
            "quando": datetime.now(timezone.utc).isoformat(),
            "conversa_id": self.conversa_id,
            "pergunta": self.pergunta,
            "ferramentas": self.ferramentas,
            "fontes": [f.get("id") for f in self.fontes],
            "resposta": self.resposta,
            "resposta_chars": len(self.resposta),
            "alertas_de_limite": self.alertas,
            "erro": self.erro,
            "duracao_s": round(time.monotonic() - self._inicio, 2),
            "modelo_roteador": config.ROTEADOR_MODELO,
            "modelo_redator": config.REDATOR_MODELO,
        }

        config.CAMINHO_LOG.parent.mkdir(parents=True, exist_ok=True)
        with _lock, config.CAMINHO_LOG.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")

        logger.info(
            "turno %s | %d ferramenta(s) | %.2fs | %s",
            self.conversa_id,
            len(self.ferramentas),
            linha["duracao_s"],
            self.erro or "ok",
        )
