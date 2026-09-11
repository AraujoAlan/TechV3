"""Monta o banco DuckDB do hospital a partir dos parquets versionados.

O notebook `07` constrói o banco inteiro, mas para isso baixa 25 arquivos do
DATASUS. O que sobe com a aplicação são os dois parquets sintéticos que ele
produz, e este módulo os transforma no DuckDB que a API consulta.

Roda no start do container e é idempotente: se o banco já existe e está mais
novo que os parquets, não faz nada.

    python -m app.hospital.montagem
"""

import sys

import duckdb

from app import config

TABELAS = ("pacientes_sinteticos", "prontuarios_sinteticos")


def precisa_montar() -> bool:
    """O banco existe e está mais novo que todos os parquets de origem?"""
    if not config.CAMINHO_DUCKDB.exists():
        return True

    banco_em = config.CAMINHO_DUCKDB.stat().st_mtime
    return any(
        (config.DIRETORIO_PUBLICADO / f"{tabela}.parquet").stat().st_mtime > banco_em
        for tabela in TABELAS
    )


def montar(forcar: bool = False) -> None:
    """Cria `config.CAMINHO_DUCKDB` a partir dos parquets de `dados_hospital/`."""
    faltando = [
        tabela
        for tabela in TABELAS
        if not (config.DIRETORIO_PUBLICADO / f"{tabela}.parquet").exists()
    ]
    if faltando:
        raise FileNotFoundError(
            f"Parquets ausentes em {config.DIRETORIO_PUBLICADO}: {', '.join(faltando)}. "
            "Eles são versionados no repositório — confira se o clone veio completo."
        )

    if not forcar and not precisa_montar():
        print(f"banco já atualizado: {config.CAMINHO_DUCKDB}")
        return

    config.CAMINHO_DUCKDB.parent.mkdir(parents=True, exist_ok=True)

    # Recriar do zero em vez de atualizar: a montagem é barata (1,6 MB) e assim
    # o banco nunca fica com sobra de uma execução anterior.
    config.CAMINHO_DUCKDB.unlink(missing_ok=True)

    con = duckdb.connect(str(config.CAMINHO_DUCKDB))
    try:
        for tabela in TABELAS:
            origem = (config.DIRETORIO_PUBLICADO / f"{tabela}.parquet").as_posix()
            con.sql(
                f"CREATE TABLE {tabela} AS SELECT * FROM read_parquet('{origem}')"
            )
            linhas = con.sql(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            print(f"  {tabela}: {linhas:,} linhas")

        # O agente quase sempre quer paciente e prontuário juntos. A view poupa
        # um JOIN escrito por LLM, que é onde ele costuma errar.
        con.sql("""
            CREATE VIEW atendimentos AS
            SELECT p.*, r.id_prontuario, r.prontuario_texto
            FROM pacientes_sinteticos p
            LEFT JOIN prontuarios_sinteticos r USING (id_paciente)
        """)
    finally:
        con.close()

    print(f"banco montado: {config.CAMINHO_DUCKDB}")


if __name__ == "__main__":
    montar(forcar="--forcar" in sys.argv)
