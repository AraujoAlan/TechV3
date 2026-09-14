"""O grafo do turno: o que ele garante, independente do que os modelos fazem.

Os dois modelos são substituídos por dublês aqui. Não é para o teste rodar
rápido — é porque o que está sob teste são exatamente as garantias que não
dependem do modelo ter acertado: caso crítico aciona a equipe, resposta crítica
sai com orientação de escalonar, resposta sem procedência não chega ao médico, e
toda passagem deixa rastro.
"""

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app import config
from app.grafo import fluxo
from app.seguranca import criticidade

PACIENTE = "PAC00000042"


class RedatorFalso:
    """Devolve respostas roteirizadas e guarda o que recebeu."""

    def __init__(self, *respostas: str):
        self.respostas = list(respostas)
        self.conversas: list[list] = []

    async def ainvoke(self, mensagens):
        self.conversas.append(mensagens)
        texto = self.respostas.pop(0) if self.respostas else "resposta padrão"
        return AIMessage(texto)


def roteador_falso(*consultas):
    """Nó que ocupa o lugar do agente e devolve as consultas indicadas.

    Cada consulta é um par `(nome_da_ferramenta, fonte)`, como o agente real
    produziria: o texto vai para o redator, e o artefato carrega a procedência.
    """

    def no(_estado, _contexto=None):
        return {
            "messages": [
                ToolMessage(
                    content=f"saída de {nome}",
                    name=nome,
                    tool_call_id=f"{nome}-{i}",
                    artifact={"fonte": fonte} if fonte else {},
                )
                for i, (nome, fonte) in enumerate(consultas)
            ]
        }

    return no


def fonte(identificador: str) -> dict:
    return {
        "id": identificador,
        "title": identificador,
        "snippet": "",
        "kind": "documento",
    }


@pytest.fixture
def montar(monkeypatch):
    """Monta um grafo com dublês, devolvendo também o redator para inspeção."""

    def _montar(
        *consultas,
        respostas=("Resposta clínica do turno.",),
        paciente=None,
        alertas=None,
    ):
        redator = RedatorFalso(*respostas)
        monkeypatch.setattr(fluxo, "criar_redator", lambda etiquetado=True: redator)

        def consultar(funcao):
            if paciente is None:
                raise ValueError("Paciente não encontrado.")
            return {"paciente": paciente, "prontuario": None}

        monkeypatch.setattr(fluxo.banco, "consultar_banco", consultar)

        registrados = alertas if alertas is not None else []
        monkeypatch.setattr(
            fluxo,
            "gravar_alerta",
            lambda **campos: (
                registrados.append(campos) or {"id": "ALERTA-TESTE"}
            ),
        )

        return fluxo.montar_grafo(roteador_falso(*consultas)), redator

    return _montar


async def rodar(grafo, pergunta: str) -> dict:
    return await grafo.ainvoke({"pergunta": pergunta, "messages": []})


# --- criticidade e alerta -----------------------------------------------------


@pytest.mark.asyncio
async def test_pergunta_geral_nao_aciona_a_equipe(montar):
    grafo, _ = montar(("consultar_banco_sql", fonte("consulta-sql")), alertas=[])

    estado = await rodar(grafo, "quais diagnósticos são mais frequentes?")

    assert estado["id_paciente"] is None
    assert not estado["criticidade"].critico
    assert estado.get("alerta_id") is None


@pytest.mark.asyncio
async def test_caso_critico_registra_alerta_com_a_regra(montar):
    alertas = []
    grafo, _ = montar(
        ("buscar_paciente", fonte(f"prontuario-{PACIENTE}")),
        paciente={
            "especialidade": "OBSTETRICIA",
            "diagnostico_principal": "O140",
            "risco_gestacional": "Alto",
        },
        alertas=alertas,
    )

    estado = await rodar(grafo, f"resuma o caso do {PACIENTE}")

    assert estado["criticidade"].codigo_regra == "MAT-OBS-001"
    assert estado["alerta_id"] == "ALERTA-TESTE"
    assert alertas[0]["codigo_regra"] == "MAT-OBS-001"
    assert alertas[0]["origem"] == "regra-de-criticidade"


@pytest.mark.asyncio
async def test_paciente_inexistente_nao_derruba_o_turno(montar):
    # O médico pode ter digitado o identificador errado. Isso vira resposta,
    # não falha de serviço.
    grafo, _ = montar(("buscar_paciente", None), paciente=None)

    estado = await rodar(grafo, f"resuma o caso do {PACIENTE}")

    assert estado["resposta"]
    assert not estado["criticidade"].critico


# --- escalonamento ------------------------------------------------------------


@pytest.mark.asyncio
async def test_resposta_critica_ganha_orientacao_de_escalonar(montar):
    grafo, _ = montar(
        ("buscar_paciente", fonte("p")),
        respostas=("Quadro compatível com pré-eclâmpsia.",),
        paciente={
            "especialidade": "OBSTETRICIA",
            "diagnostico_principal": "O14",
        },
    )

    estado = await rodar(grafo, f"avalie o {PACIENTE}")

    assert fluxo.limites.AVISO_ESCALONAMENTO in estado["resposta"]


@pytest.mark.asyncio
async def test_nao_duplica_orientacao_que_o_redator_ja_deu(montar):
    grafo, _ = montar(
        ("buscar_paciente", fonte("p")),
        respostas=("Quadro grave: acionar a equipe de plantão agora.",),
        paciente={
            "especialidade": "OBSTETRICIA",
            "diagnostico_principal": "O14",
        },
    )

    estado = await rodar(grafo, f"avalie o {PACIENTE}")

    assert fluxo.limites.AVISO_ESCALONAMENTO not in estado["resposta"]
    assert "acionar a equipe" in estado["resposta"]


# --- validação ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_protocolo_sem_consulta_nao_chega_ao_medico(montar, monkeypatch):
    monkeypatch.setattr(config, "MAX_REVISOES", 0)
    grafo, _ = montar(
        ("consultar_banco_sql", fonte("sql")),
        respostas=("Conforme o protocolo interno do hospital, conduza assim.",),
    )

    estado = await rodar(grafo, "o que fazer nesse caso?")

    assert estado["resposta"] == fluxo.limites.MENSAGEM_LIMITACAO
    assert estado["violacoes"]


@pytest.mark.asyncio
async def test_com_orcamento_o_redator_reescreve_sabendo_o_motivo(
    montar, monkeypatch
):
    monkeypatch.setattr(config, "MAX_REVISOES", 1)
    grafo, redator = montar(
        ("consultar_banco_sql", fonte("sql")),
        respostas=(
            "Conforme o protocolo interno do hospital, conduza assim.",
            "Sem protocolo consultado, sigo o que o prontuário registra.",
        ),
    )

    estado = await rodar(grafo, "o que fazer nesse caso?")

    assert estado["resposta"].startswith("Sem protocolo consultado")
    assert estado["revisao"] == 1
    # A segunda conversa tem que carregar o que reprovou a primeira, senão a
    # reescrita repete o erro e queima o orçamento à toa.
    segunda = str(redator.conversas[1][-1].content)
    assert "correções exigidas" in segunda


@pytest.mark.asyncio
async def test_resposta_vazia_e_reprovada(montar):
    grafo, _ = montar(("consultar_banco_sql", fonte("sql")), respostas=("   ",))

    estado = await rodar(grafo, "o que fazer?")

    assert estado["resposta"] == fluxo.limites.MENSAGEM_LIMITACAO


# --- procedência e falhas -----------------------------------------------------


@pytest.mark.asyncio
async def test_fontes_repetidas_aparecem_uma_vez(montar):
    grafo, _ = montar(
        ("buscar_paciente", fonte("prontuario-x")),
        ("buscar_paciente", fonte("prontuario-x")),
        ("consultar_protocolo", fonte("PROT-01")),
    )

    estado = await rodar(grafo, "pergunta")

    assert [f["id"] for f in estado["fontes"]] == ["prontuario-x", "PROT-01"]


@pytest.mark.asyncio
async def test_falha_do_redator_vira_saida_segura(montar, monkeypatch):
    grafo, _ = montar(("consultar_banco_sql", fonte("sql")))

    class RedatorQuebrado:
        async def ainvoke(self, _mensagens):
            raise RuntimeError("llama-server fora do ar")

    monkeypatch.setattr(
        fluxo, "criar_redator", lambda etiquetado=True: RedatorQuebrado()
    )

    estado = await rodar(grafo, "pergunta")

    assert estado["resposta"] == fluxo.limites.MENSAGEM_LIMITACAO
    assert estado["codigo_erro"] == "RuntimeError"


@pytest.mark.asyncio
async def test_cada_no_deixa_rastro_na_auditoria(montar):
    grafo, _ = montar(("consultar_banco_sql", fonte("sql")))

    class RegistroFalso:
        def __init__(self):
            self.eventos = []

        def registrar_evento(self, *, no, evento, detalhes, chave):
            self.eventos.append((no, evento, chave))

    registro = RegistroFalso()
    await grafo.ainvoke(
        {"pergunta": "pergunta", "messages": []},
        config={"configurable": {"registro": registro}},
    )

    nos = {no for no, _evento, _chave in registro.eventos}
    assert {"inicializar", "identificar", "coletar", "criticidade", "gerar"} <= nos
    assert all(
        evento in {"iniciado", "concluido", "falhou"}
        for _no, evento, _chave in registro.eventos
    )
    # A chave de idempotência precisa ser única por evento, senão a auditoria
    # perde passagens do laço de revisão.
    chaves = [chave for _no, _evento, chave in registro.eventos]
    assert len(chaves) == len(set(chaves))
