"""Configuração da aplicação, lida do ambiente.

Tudo que muda entre a máquina do grupo e o docker compose mora aqui. Os valores
padrão são os do desenvolvimento local, então `python -m app` sobe sem `.env`
desde que a chave do roteador esteja no ambiente.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent


def _caminho(variavel: str, padrao: Path) -> Path:
    valor = os.getenv(variavel)
    return Path(valor) if valor else padrao


# --- Banco -------------------------------------------------------------------
# Os parquets versionados (saída do notebook 07) e o DuckDB montado a partir
# deles no start da aplicação.
DIRETORIO_PUBLICADO = _caminho("DIRETORIO_PUBLICADO", RAIZ / "dados_hospital")
CAMINHO_DUCKDB = _caminho("CAMINHO_DUCKDB", RAIZ / "data" / "hospital.duckdb")

# Teto de linhas devolvido por consulta. Existe para proteger a janela de
# contexto do redator, não o banco: 500 linhas de prontuário estouram o prompt.
MAX_LINHAS_CONSULTA = int(os.getenv("MAX_LINHAS_CONSULTA", "20"))

# --- Roteador: decide quais tools chamar --------------------------------------
ROTEADOR_BASE_URL = os.getenv("ROTEADOR_BASE_URL", "https://api.z.ai/api/paas/v4/")
ROTEADOR_MODELO = os.getenv("ROTEADOR_MODELO", "glm-5.3-flash")
ROTEADOR_API_KEY = os.getenv("Z_API_KEY", "")
ROTEADOR_MAX_PASSOS = int(os.getenv("ROTEADOR_MAX_PASSOS", "6"))

# --- Redator: o modelo fine-tunado, escreve a resposta ------------------------
# Aponta para o llama-server, que expõe API compatível com a da OpenAI.
REDATOR_BASE_URL = os.getenv("REDATOR_BASE_URL", "http://localhost:8080/v1")
REDATOR_MODELO = os.getenv("REDATOR_MODELO", "assistente-maternidade")
REDATOR_API_KEY = os.getenv("REDATOR_API_KEY", "nao-usada")  # llama-server ignora
REDATOR_TEMPERATURA = float(os.getenv("REDATOR_TEMPERATURA", "0.3"))
REDATOR_MAX_TOKENS = int(os.getenv("REDATOR_MAX_TOKENS", "800"))

# --- Auditoria ----------------------------------------------------------------
CAMINHO_LOG = _caminho("CAMINHO_LOG", RAIZ / "logs" / "auditoria.jsonl")

# --- Frontend -----------------------------------------------------------------
# O build do Vite. Quando existe, a API serve a interface na mesma origem, que
# é o que o contrato do frontend assume (sem CORS).
DIRETORIO_FRONTEND = _caminho("DIRETORIO_FRONTEND", RAIZ / "frontend" / "dist")
