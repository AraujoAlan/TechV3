"""Acesso somente-leitura ao banco de prontuários do hospital.

A `FerramentaConsultaSIH` abaixo vem do notebook `07_banco_sih.ipynb`, de Caê
Euphrasio, intacta: mudaram só o caminho padrão do banco, que passou a vir da
config, e a mensagem de erro quando o arquivo não existe.

Ela já tinha sido escrita pensando em uso por agente — conexão `read_only`,
consulta livre restrita a `SELECT`/`WITH`, `LIMIT` de segurança injetado — que é
exatamente a garantia de que precisamos ao deixar uma LLM escrever o SQL. O
`read_only=True` é a defesa que sustenta as outras: mesmo que o filtro de
comando falhasse, o DuckDB recusaria a escrita.
"""

import threading
from pathlib import Path

import duckdb
import pandas as pd

from app import config


class FerramentaConsultaSIH:
    """Ferramenta de consulta somente-leitura ao banco DuckDB gerado pelo pipeline."""

    def __init__(self, caminho_banco: str | Path | None = None):
        self.caminho_banco = Path(caminho_banco or config.CAMINHO_DUCKDB)
        if not self.caminho_banco.exists():
            raise FileNotFoundError(
                f"Banco DuckDB não encontrado em '{self.caminho_banco}'. "
                "Rode `python -m app.hospital.montagem` para montá-lo a partir "
                "dos parquets de dados_hospital/."
            )
        self._con = duckdb.connect(str(self.caminho_banco), read_only=True)

    # --- suporte a "with FerramentaConsultaSIH() as ferramenta:" ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fechar()

    def fechar(self):
        """Fecha a conexão somente-leitura."""
        self._con.close()

    def tabelas(self) -> list[str]:
        """Lista as tabelas e views disponíveis no banco."""
        df = self._con.sql("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).df()
        return df["table_name"].tolist()

    def descrever(self, tabela: str) -> pd.DataFrame:
        """Mostra colunas e tipos de uma tabela."""
        self._validar_nome_tabela(tabela)
        return self._con.sql(f"DESCRIBE {tabela}").df()

    def consultar(self, sql: str, limite: int = 500) -> pd.DataFrame:
        """
        Executa uma consulta SQL livre, mas SOMENTE leitura (SELECT ou CTE
        iniciada por WITH). Qualquer outro comando é rejeitado — pensado
        para uso seguro por um agente automatizado.
        """
        sql_normalizado = sql.strip().rstrip(";")
        primeira_palavra = sql_normalizado.split(None, 1)[0].upper() if sql_normalizado else ""

        if primeira_palavra not in ("SELECT", "WITH"):
            raise ValueError(
                "Somente consultas SELECT (ou WITH ... SELECT) são permitidas "
                "nesta ferramenta de consulta somente-leitura."
            )

        # Aplica um limite de segurança caso a consulta não tenha um.
        if "LIMIT" not in sql_normalizado.upper():
            sql_normalizado = f"SELECT * FROM ({sql_normalizado}) AS _sub LIMIT {limite}"

        return self._con.sql(sql_normalizado).df()

    def estatisticas_especialidade(self) -> pd.DataFrame:
        """Distribuição de pacientes sintéticos por especialidade."""
        return self._con.sql("""
            SELECT
                especialidade,
                COUNT(*) AS quantidade,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS percentual
            FROM pacientes_sinteticos
            GROUP BY especialidade
            ORDER BY quantidade DESC
        """).df()

    def estatisticas_diagnostico(self, especialidade: str | None = None, top: int = 10) -> pd.DataFrame:
        """Diagnósticos mais frequentes, opcionalmente filtrados por especialidade."""
        filtro = ""
        if especialidade is not None:
            especialidade_escapada = especialidade.replace("'", "''")
            filtro = f"WHERE especialidade = '{especialidade_escapada}'"

        return self._con.sql(f"""
            SELECT especialidade, diagnostico_principal, COUNT(*) AS quantidade
            FROM pacientes_sinteticos
            {filtro}
            GROUP BY especialidade, diagnostico_principal
            ORDER BY quantidade DESC
            LIMIT {top}
        """).df()

    def amostra_prontuarios(self, especialidade: str | None = None, n: int = 3) -> pd.DataFrame:
        """Retorna N prontuários de exemplo, opcionalmente filtrados por especialidade."""
        filtro = ""
        if especialidade is not None:
            especialidade_escapada = especialidade.replace("'", "''")
            filtro = f"WHERE especialidade = '{especialidade_escapada}'"

        return self._con.sql(f"""
            SELECT id_prontuario, id_paciente, especialidade, prontuario_texto
            FROM prontuarios_sinteticos
            {filtro}
            USING SAMPLE {n}
        """).df()

    def buscar_paciente(self, id_paciente: str) -> dict:
        """Retorna o perfil clínico e o prontuário de um paciente específico."""
        id_escapado = id_paciente.replace("'", "''")

        paciente_df = self._con.sql(f"""
            SELECT * FROM pacientes_sinteticos WHERE id_paciente = '{id_escapado}'
        """).df()

        prontuario_df = self._con.sql(f"""
            SELECT * FROM prontuarios_sinteticos WHERE id_paciente = '{id_escapado}'
        """).df()

        if paciente_df.empty:
            raise ValueError(f"Paciente '{id_paciente}' não encontrado.")

        return {
            "paciente": paciente_df.iloc[0].to_dict(),
            "prontuario": prontuario_df.iloc[0].to_dict() if not prontuario_df.empty else None,
        }

    @staticmethod
    def _validar_nome_tabela(tabela: str):
        """Validação simples para evitar injeção de SQL em nomes de tabela."""
        if not tabela.replace("_", "").isalnum():
            raise ValueError(f"Nome de tabela inválido: '{tabela}'")


# --- acesso compartilhado -----------------------------------------------------
# A aplicação usa uma instância só. O DuckDB aceita várias conexões de leitura
# sobre o mesmo arquivo, mas uma conexão não é segura entre threads — e as tools
# rodam no executor de threads do LangChain. Daí o lock.

_banco: FerramentaConsultaSIH | None = None
_lock = threading.RLock()  # reentrante: consultar_banco() chama abrir_banco()


def abrir_banco() -> FerramentaConsultaSIH:
    """Devolve a instância compartilhada, abrindo o arquivo na primeira chamada."""
    global _banco
    with _lock:
        if _banco is None:
            _banco = FerramentaConsultaSIH()
        return _banco


def consultar_banco(funcao):
    """Executa `funcao(banco)` com exclusão mútua sobre a conexão."""
    with _lock:
        return funcao(abrir_banco())


def fechar_banco() -> None:
    """Fecha a conexão compartilhada. Usado no shutdown da API e nos testes."""
    global _banco
    with _lock:
        if _banco is not None:
            _banco.fechar()
            _banco = None
