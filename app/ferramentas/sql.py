"""Tools de consulta ao banco do hospital, expostas ao roteador.

São a "consulta em base de dados estruturada" que a fase pede. Quem executa é a
`FerramentaConsultaSIH` (`app/hospital/banco.py`), que já abre o arquivo em
somente-leitura e recusa qualquer comando que não seja `SELECT`/`WITH`.

Cada tool devolve `(texto, artefato)`: o texto vai para o modelo, e o artefato
carrega a fonte — qual tabela, qual paciente, qual SQL — que o grafo transforma
no evento `sources` da resposta. É assim que a resposta fica auditável: dá para
apontar de onde saiu cada número.

Duas restrições moldam o formato de saída:

- **Linhas.** O teto existe para proteger a janela de contexto do redator, não o
  banco. Vinte prontuários inteiros são ~25 mil caracteres.
- **Entradas planas.** A trilha de tools da interface renderiza os argumentos com
  `String(value)`, então um objeto aninhado apareceria como `[object Object]`.
"""

import pandas as pd
from langchain_core.tools import tool

from app import config
from app.hospital import banco

# Prontuário inteiro dentro de uma célula de tabela é ilegível e caro. Quem
# quiser o texto completo usa `buscar_paciente`.
MAX_CHARS_CELULA = 300


def _tabela_para_texto(df: pd.DataFrame) -> str:
    """Formata um resultado para leitura pelo modelo, com os cortes declarados.

    Espera receber até uma linha a mais do que se pretende mostrar: é assim que
    a função descobre que houve corte. Sem essa linha extra o `LIMIT` do SQL já
    teria devolvido exatamente o teto, e o corte seria invisível aqui — o modelo
    leria vinte linhas achando que são todas, e responderia "o hospital tem
    vinte casos" sobre um banco de dez mil.
    """
    if df.empty:
        return "A consulta não retornou nenhuma linha."

    total = len(df)
    df = df.head(config.MAX_LINHAS_CONSULTA).copy()

    # O corte é decidido pelo valor, e não pelo dtype da coluna. Checar
    # `dtype == object` aqui deixava o pandas 3 passar batido: colunas de texto
    # passaram a ter dtype `str`, o corte parava de rodar, e vinte prontuários
    # inteiros seguiam para o prompt do redator.
    for coluna in df.columns:
        df[coluna] = df[coluna].apply(
            lambda v: (
                v[:MAX_CHARS_CELULA] + "…"
                if isinstance(v, str) and len(v) > MAX_CHARS_CELULA
                else v
            )
        )

    texto = df.to_string(index=False)
    if total > len(df):
        # Sem afirmar um total: a linha extra prova que há mais, mas não diz
        # quantas. Inventar o número aqui seria pior que não dizer.
        texto += (
            f"\n\n[mostrando as primeiras {len(df)} linhas; a consulta retornou "
            "mais. Use agregação ou filtro para alcançar o resto.]"
        )
    return texto


def _fonte(identificador: str, titulo: str, trecho: str, tipo: str) -> dict:
    return {
        "fonte": {
            "id": identificador,
            "title": titulo,
            "snippet": trecho,
            "kind": tipo,
        }
    }


@tool(response_format="content_and_artifact")
def descrever_banco() -> tuple[str, dict]:
    """Lista as tabelas do banco do hospital e as colunas de cada uma.

    Use antes de escrever SQL, para conferir os nomes reais das colunas.
    """

    def executar(ferramenta):
        partes = []
        for tabela in ferramenta.tabelas():
            colunas = ferramenta.descrever(tabela)
            descricao = ", ".join(
                f"{linha.column_name} ({linha.column_type})"
                for linha in colunas.itertuples()
            )
            partes.append(f"{tabela}: {descricao}")
        return partes

    partes = banco.consultar_banco(executar)
    texto = (
        "\n\n".join(partes)
        + "\n\nA view `atendimentos` já junta paciente e prontuário pelo id_paciente."
    )
    return texto, _fonte(
        "banco-esquema",
        "Esquema do banco do hospital",
        f"{len(partes)} tabelas disponíveis",
        "documento",
    )


@tool(response_format="content_and_artifact")
def consultar_banco_sql(sql: str) -> tuple[str, dict]:
    """Executa uma consulta SQL de leitura no banco do hospital (dialeto DuckDB).

    Aceita apenas SELECT ou WITH. Consulte `descrever_banco` antes, para usar os
    nomes corretos de coluna. Prefira agregações a listar muitas linhas.

    Args:
        sql: a consulta a executar, em uma instrução só.
    """
    try:
        df = banco.consultar_banco(
            lambda ferramenta: ferramenta.consultar(
                sql, limite=config.MAX_LINHAS_CONSULTA + 1
            )
        )
    except ValueError as erro:
        # Comando recusado pela camada somente-leitura: o modelo consegue
        # corrigir a própria consulta se souber o motivo.
        return f"Consulta recusada: {erro}", _fonte(
            "consulta-recusada", "Consulta SQL recusada", str(erro), "documento"
        )
    except Exception as erro:  # erro de sintaxe, coluna inexistente, etc.
        return (
            f"A consulta falhou: {erro}\n\n"
            "Use `descrever_banco` para conferir tabelas e colunas.",
            _fonte("consulta-falhou", "Consulta SQL com erro", str(erro)[:200], "documento"),
        )

    return _tabela_para_texto(df), _fonte(
        "consulta-sql",
        "Consulta ao banco do hospital",
        sql.strip(),
        "documento",
    )


@tool(response_format="content_and_artifact")
def buscar_paciente(id_paciente: str) -> tuple[str, dict]:
    """Busca o perfil clínico e o prontuário completo de um paciente.

    Args:
        id_paciente: identificador no formato PAC00000001.
    """
    try:
        registro = banco.consultar_banco(
            lambda ferramenta: ferramenta.buscar_paciente(id_paciente)
        )
    except ValueError as erro:
        return str(erro), _fonte(
            "paciente-inexistente",
            f"Paciente {id_paciente} não encontrado",
            str(erro),
            "prontuario",
        )

    paciente = registro["paciente"]
    prontuario = registro["prontuario"]

    # Campos vazios são os da especialidade que não se aplica ao paciente
    # (obstétricos num caso pediátrico, por exemplo). Listar tudo só polui.
    perfil = "\n".join(
        f"{chave}: {valor}"
        for chave, valor in paciente.items()
        if valor is not None and not pd.isna(valor)
    )

    texto = f"PERFIL\n{perfil}"
    if prontuario is not None:
        texto += f"\n\nPRONTUÁRIO\n{prontuario['prontuario_texto']}"

    return texto, _fonte(
        f"prontuario-{id_paciente}",
        f"Prontuário do paciente {id_paciente}",
        f"{paciente.get('especialidade')} — {paciente.get('diagnostico_principal')}",
        "prontuario",
    )


@tool(response_format="content_and_artifact")
def estatisticas_de_diagnosticos(especialidade: str = "") -> tuple[str, dict]:
    """Diagnósticos mais frequentes no hospital, em código CID-10.

    Args:
        especialidade: OBSTETRICIA, GINECOLOGIA ou PEDIATRIA. Vazio traz todas.
    """
    filtro = especialidade.strip().upper() or None

    df = banco.consultar_banco(
        lambda ferramenta: ferramenta.estatisticas_diagnostico(
            especialidade=filtro, top=config.MAX_LINHAS_CONSULTA + 1
        )
    )

    alvo = filtro or "todas as especialidades"
    return _tabela_para_texto(df), _fonte(
        f"estatisticas-{alvo.lower().replace(' ', '-')}",
        f"Diagnósticos mais frequentes — {alvo}",
        "Contagem sobre os atendimentos registrados no banco do hospital.",
        "documento",
    )


FERRAMENTAS_SQL = [
    descrever_banco,
    consultar_banco_sql,
    buscar_paciente,
    estatisticas_de_diagnosticos,
]
