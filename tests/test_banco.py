"""O banco do hospital e as ferramentas que o consultam.

O foco é o que protege o banco de uma LLM escrevendo SQL. O `read_only=True` da
conexão é a garantia real; os testes abaixo verificam que ela está de pé junto
com o filtro de comando, e que uma consulta recusada devolve texto explicando o
motivo em vez de estourar — senão o modelo não tem como se corrigir.
"""

import duckdb
import pytest

from app import config
from app.hospital import banco, montagem


@pytest.fixture(scope="module")
def hospital():
    montagem.montar()
    yield banco.abrir_banco()
    banco.fechar_banco()


def chamar(ferramenta, **argumentos):
    """Invoca a tool como o agente invoca, para receber também o artefato."""
    mensagem = ferramenta.invoke(
        {
            "type": "tool_call",
            "name": ferramenta.name,
            "args": argumentos,
            "id": "teste",
        }
    )
    return mensagem.content, mensagem.artifact


def test_montagem_cria_as_tabelas_e_a_view(hospital):
    assert set(hospital.tabelas()) == {
        "pacientes_sinteticos",
        "prontuarios_sinteticos",
        "atendimentos",
    }


def test_banco_tem_os_dez_mil_atendimentos(hospital):
    total = hospital.consultar("SELECT COUNT(*) AS n FROM pacientes_sinteticos")
    assert total["n"][0] == 10_000


def test_view_atendimentos_junta_paciente_e_prontuario(hospital):
    linha = hospital.consultar(
        "SELECT * FROM atendimentos WHERE id_paciente = 'PAC00000001'"
    ).iloc[0]
    assert linha["especialidade"] == "OBSTETRICIA"
    assert "PRONTUÁRIO CLÍNICO" in linha["prontuario_texto"]


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE pacientes_sinteticos",
        "DELETE FROM pacientes_sinteticos",
        "INSERT INTO pacientes_sinteticos VALUES ('x')",
        "UPDATE pacientes_sinteticos SET idade = 0",
        "CREATE TABLE invadido (a INT)",
        "ATTACH 'outro.db' AS outro",
    ],
)
def test_escrita_e_recusada(hospital, sql):
    with pytest.raises(ValueError, match="Somente consultas SELECT"):
        hospital.consultar(sql)


def test_conexao_e_somente_leitura_mesmo_por_fora_do_filtro(hospital):
    """A defesa que sustenta as outras: nem o DuckDB aceitaria a escrita.

    Se o filtro de comando falhasse, esta é a camada que ainda segura.
    """
    with pytest.raises(duckdb.Error):
        hospital._con.sql("CREATE TABLE invadido (a INT)")


def test_limite_e_aplicado_quando_a_consulta_nao_traz_um(hospital):
    linhas = hospital.consultar("SELECT * FROM pacientes_sinteticos", limite=7)
    assert len(linhas) == 7


def test_consulta_recusada_vira_texto_e_nao_excecao():
    """O agente precisa conseguir ler o erro para reescrever o SQL."""
    from app.ferramentas.sql import consultar_banco_sql

    conteudo, _ = chamar(consultar_banco_sql, sql="DROP TABLE pacientes_sinteticos")
    assert "recusada" in conteudo.lower()


def test_sql_invalido_orienta_a_conferir_o_esquema():
    from app.ferramentas.sql import consultar_banco_sql

    conteudo, _ = chamar(consultar_banco_sql, sql="SELECT * FROM nao_existe")
    assert "descrever_banco" in conteudo


def test_paciente_inexistente_nao_inventa_resposta():
    from app.ferramentas.sql import buscar_paciente

    conteudo, artefato = chamar(buscar_paciente, id_paciente="PAC99999999")
    assert "não encontrado" in conteudo
    assert artefato["fonte"]["id"] == "paciente-inexistente"


def test_toda_ferramenta_devolve_fonte_para_a_explicabilidade(hospital):
    """Sem fonte no artefato, a resposta não tem como citar de onde veio."""
    from app.ferramentas.sql import FERRAMENTAS_SQL

    argumentos = {
        "descrever_banco": {},
        "consultar_banco_sql": {"sql": "SELECT 1 AS um"},
        "buscar_paciente": {"id_paciente": "PAC00000001"},
        "estatisticas_de_diagnosticos": {"especialidade": "PEDIATRIA"},
    }

    for ferramenta in FERRAMENTAS_SQL:
        _, artefato = chamar(ferramenta, **argumentos[ferramenta.name])
        fonte = artefato["fonte"]
        assert fonte["id"] and fonte["title"], ferramenta.name
        assert fonte["kind"] in {"protocolo", "prontuario", "exame", "documento"}


def test_resultado_grande_e_cortado_para_caber_no_contexto(hospital):
    """Vinte prontuários inteiros passam de 25 mil caracteres."""
    from app.ferramentas.sql import consultar_banco_sql

    conteudo, _ = chamar(
        consultar_banco_sql,
        sql="SELECT prontuario_texto FROM prontuarios_sinteticos",
    )
    assert len(conteudo) < 15_000
    assert f"de {10_000:,}".replace(",", ",") in conteudo or "mostrando" in conteudo


def test_parquets_versionados_existem():
    """Se estes sumirem, o compose sobe sem banco."""
    for tabela in montagem.TABELAS:
        assert (config.DIRETORIO_PUBLICADO / f"{tabela}.parquet").exists()
