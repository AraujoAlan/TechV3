"""O fluxo do turno, como um `StateGraph`.

A espinha deste grafo — auditoria por nó com chave de idempotência, avaliação de
criticidade antes de redigir, escalonamento obrigatório e o laço
gerar → validar → gerar — vem do fluxo LangGraph escrito por Igor Pestana. O que
mudou na integração foi de onde vêm os dados.

**Recuperação.** O desenho original tinha três nós fixos (`record`, `exams`,
`protocol`) chamando métodos tipados de um repositório. Aqui esses três nós dão
lugar a um só, que roda o agente roteador com as ferramentas do repositório: o
GLM decide o que consultar e escreve o SQL. É o que mantém viva a consulta livre
à base estruturada — o banco tem 10 mil prontuários e 9 protocolos, e uma
interface de três métodos fixos não alcança isso.

O preço é que a recuperação deixa de ser determinística. O controle volta abaixo
dela: criticidade, escalonamento e validação continuam em código, e nenhum deles
pergunta nada a um modelo.

**Crítica por LLM.** O desenho original tinha um nó `critique` que pedia a um
modelo generalista para apontar problemas na resposta, e alimentava o validador
com isso. Ele não sobreviveu: o validador desta integração é inteiramente
determinístico (ver `app/seguranca/limites.py`), então a crítica não teria
consumidor — seria uma ida ao modelo cujo resultado ninguém lê.
"""

import inspect
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app import config as configuracao
from app.ferramentas.alertas import gravar_alerta
from app.grafo.estado import EstadoDoTurno
from app.grafo.prompts import SYSTEM_ASSISTENTE, montar_pergunta_com_contexto
from app.hospital import banco
from app.llm.redator import criar_redator
from app.seguranca import criticidade as regras
from app.seguranca import limites

# Como os identificadores aparecem no banco deste hospital. O fluxo original
# procurava o formato `P-042` do banco de demonstração; aqui são 10 mil
# pacientes gerados pelo pipeline do SIH/SUS.
PADRAO_ID_PACIENTE = re.compile(r"\bPAC\d{8}\b", re.IGNORECASE)


# --- auditoria ----------------------------------------------------------------


def _registro(config) -> object | None:
    """O `RegistroDoTurno` do turno, quando a API o injetou.

    Fora da API — em teste, ou num script — o grafo roda sem registro. Os nós
    funcionam igual; só não há linha de auditoria para gravar.
    """
    return (config or {}).get("configurable", {}).get("registro")


def _anotador(nome: str, estado: EstadoDoTurno, config):
    """Devolve a função que grava os eventos deste nó nesta passagem.

    A chave de idempotência inclui a tentativa de revisão porque o laço passa
    por `gerar` mais de uma vez: sem ela, a segunda passagem seria descartada
    como repetição, e a auditoria mostraria um fluxo que não aconteceu.
    """
    registro = _registro(config)
    tentativa = estado.get("revisao", 0)
    turno_id = estado.get("turno_id", "?")

    def anotar(evento: str, detalhes: dict) -> None:
        if registro is not None:
            registro.registrar_evento(
                no=nome,
                evento=evento,
                detalhes=detalhes,
                chave=f"{turno_id}:{nome}:{tentativa}:{evento}",
            )

    return anotar


def auditado(nome: str, no):
    """Envolve um nó para que ele deixe rastro na auditoria.

    Há duas versões porque `gerar` é assíncrono — ele espera o redator — e os
    demais nós não são. Um envelope só, síncrono, devolveria a corotina de
    `gerar` sem aguardá-la: o grafo receberia um objeto no lugar do resultado e
    a resposta nunca seria escrita.
    """
    if inspect.iscoroutinefunction(no):

        async def invocar_async(estado: EstadoDoTurno, config=None):
            anotar = _anotador(nome, estado, config)
            anotar("iniciado", {})
            try:
                resultado = await no(estado, config) or {}
            except Exception as erro:  # noqa: BLE001 — a falha vira saída segura
                anotar("falhou", {"erro": f"{type(erro).__name__}: {erro}"})
                return {"codigo_erro": type(erro).__name__}

            anotar("concluido", _detalhes_do_resultado(nome, resultado))
            return resultado

        return invocar_async

    def invocar(estado: EstadoDoTurno, config=None):
        anotar = _anotador(nome, estado, config)
        anotar("iniciado", {})
        try:
            resultado = no(estado, config) or {}
        except Exception as erro:  # noqa: BLE001 — a falha vira saída segura
            anotar("falhou", {"erro": f"{type(erro).__name__}: {erro}"})
            return {"codigo_erro": type(erro).__name__}

        anotar("concluido", _detalhes_do_resultado(nome, resultado))
        return resultado

    return invocar


def _detalhes_do_resultado(nome: str, resultado: dict) -> dict:
    """O que vale registrar da saída de cada nó, sem copiar a resposta inteira."""
    if nome == "criticidade":
        avaliacao = resultado.get("criticidade")
        return avaliacao.como_dicionario() if avaliacao else {}

    if nome == "validar":
        violacoes = resultado.get("violacoes", [])
        return {
            "violacoes": len(violacoes),
            "detalhe": " | ".join(violacoes),
            "revisao": resultado.get("revisao", 0),
        }

    if nome == "alerta":
        return {"alerta_id": resultado.get("alerta_id")}

    if resultado.get("codigo_erro"):
        return {"codigo_erro": resultado["codigo_erro"]}

    return {}


# --- nós ----------------------------------------------------------------------


def inicializar(estado: EstadoDoTurno, config=None) -> dict:
    """Abre o turno e coloca a pergunta no formato que o roteador consome."""
    return {
        "turno_id": str(uuid.uuid4()),
        "revisao": 0,
        "fontes": [],
        "ferramentas_usadas": [],
        "violacoes": [],
        "codigo_erro": None,
        "messages": [HumanMessage(estado["pergunta"])],
    }


def identificar_paciente(estado: EstadoDoTurno, config=None) -> dict:
    """Procura um identificador de paciente na pergunta.

    É de propósito que isto seja uma expressão regular e não uma chamada a
    modelo. O identificador decide se haverá avaliação de criticidade e se um
    alerta pode ser emitido — não é lugar para uma extração probabilística.
    Quando o médico não cita paciente, a pergunta é geral e o fluxo segue sem
    caso clínico em curso.
    """
    achado = PADRAO_ID_PACIENTE.search(estado.get("pergunta", ""))
    return {"id_paciente": achado.group(0).upper() if achado else None}


def coletar_recuperacao(estado: EstadoDoTurno, config=None) -> dict:
    """Lê o que o roteador consultou e separa fontes e ferramentas usadas.

    As fontes saem do artefato de cada ferramenta — dado produzido por código,
    não texto gerado por modelo. É essa procedência que sustenta o evento
    `sources` do contrato: dá para apontar de qual consulta saiu cada número.
    """
    fontes: list[dict] = []
    ferramentas: list[str] = []

    for mensagem in estado.get("messages", []):
        if not isinstance(mensagem, ToolMessage):
            continue

        if mensagem.name:
            ferramentas.append(mensagem.name)

        fonte = (mensagem.artifact or {}).get("fonte")
        if fonte:
            fontes.append(fonte)

    return {"fontes": fontes, "ferramentas_usadas": ferramentas}


def avaliar_criticidade(estado: EstadoDoTurno, config=None) -> dict:
    """Classifica o caso a partir do registro estruturado do paciente.

    Consulta o banco de novo, em vez de reaproveitar o que o roteador trouxe, e
    isso é deliberado: o que chega do roteador é texto formatado para o modelo
    ler. A regra precisa dos campos como o banco os guarda.
    """
    id_paciente = estado.get("id_paciente")
    if not id_paciente:
        return {"criticidade": regras.NAO_CRITICO}

    try:
        registro = banco.consultar_banco(
            lambda ferramenta: ferramenta.buscar_paciente(id_paciente)
        )
    except ValueError:
        # Paciente citado que não existe no banco. Não é erro de serviço: o
        # médico pode ter digitado errado, e a resposta deve dizer isso.
        return {"criticidade": regras.NAO_CRITICO}

    return {"criticidade": regras.avaliar(registro["paciente"])}


def alertar_equipe(estado: EstadoDoTurno, config=None) -> dict:
    """Registra o alerta que a regra de criticidade disparou."""
    avaliacao: regras.Criticidade = estado["criticidade"]

    registro = gravar_alerta(
        id_paciente=estado["id_paciente"],
        mensagem=avaliacao.motivo or "Caso classificado como crítico.",
        prioridade="emergencia",
        origem="regra-de-criticidade",
        codigo_regra=avaliacao.codigo_regra,
        versao_regra=avaliacao.versao_regra,
    )

    return {"alerta_id": registro["id"]}


def montar_conversa_do_redator(estado: EstadoDoTurno) -> list:
    """Reconstrói a conversa como o modelo fine-tunado espera vê-la.

    O que há no estado é o rascunho do roteador: pergunta, decisões de tool call
    e resultados de ferramenta, tudo misturado. O modelo fine-tunado nunca viu
    isso no treino — ele viu system, pergunta, resposta. Então a conversa é
    remontada nesse formato, com o que as ferramentas trouxeram anexado à
    pergunta do turno.
    """
    mensagens = estado.get("messages", [])
    corte = max(
        (i for i, m in enumerate(mensagens) if isinstance(m, HumanMessage)),
        default=0,
    )
    pergunta = mensagens[corte].content if mensagens else estado.get("pergunta", "")

    # Histórico: só as falas de verdade. Tool call e resultado de ferramenta de
    # turnos passados não entram — são o caderno de rascunho do roteador.
    historico = [
        m
        for m in mensagens[:corte]
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and m.content and not m.tool_calls)
    ]

    resultados = [m for m in mensagens[corte:] if isinstance(m, ToolMessage)]
    contexto = "\n\n".join(
        f"[{m.name}]\n{m.content}" for m in resultados if str(m.content).strip()
    )

    violacoes = estado.get("violacoes", [])
    if violacoes:
        # A segunda tentativa precisa saber o que reprovou a primeira, senão ela
        # reescreve o mesmo texto e queima o orçamento de revisão à toa.
        contexto += "\n\n[correções exigidas]\n" + "\n".join(
            f"- {violacao}" for violacao in violacoes
        )

    return [
        SystemMessage(SYSTEM_ASSISTENTE),
        *historico,
        HumanMessage(montar_pergunta_com_contexto(pergunta, contexto)),
    ]


async def gerar(estado: EstadoDoTurno, config=None) -> dict:
    """O modelo fine-tunado escreve a resposta ao médico.

    A etiqueta do redator só é aplicada quando não há revisão configurada. Com
    revisão ligada, um rascunho pode ser reprovado depois de já ter sido
    transmitido, e o médico teria lido um texto que o grafo descartou — então os
    tokens ficam retidos e a resposta aprovada é emitida de uma vez.
    """
    redator = criar_redator(etiquetado=configuracao.MAX_REVISOES == 0)
    resposta = await redator.ainvoke(montar_conversa_do_redator(estado))
    return {"rascunho": str(resposta.content)}


def escalonar(estado: EstadoDoTurno, config=None) -> dict:
    """Garante que todo caso crítico oriente acionar a equipe.

    O redator costuma fazer isso sozinho quando o config deixa claro. Quando
    não faz, o aviso é anexado — porque a fase exige que o caso crítico escale,
    e "o modelo geralmente lembra" não é uma garantia que se possa auditar.
    """
    avaliacao: regras.Criticidade = estado.get("criticidade", regras.NAO_CRITICO)
    rascunho = estado.get("rascunho", "").strip()

    if not avaliacao.critico or limites.PADRAO_ESCALONAMENTO.search(rascunho):
        return {"rascunho": rascunho}

    return {"rascunho": f"{rascunho}\n\n{limites.AVISO_ESCALONAMENTO}"}


def validar(estado: EstadoDoTurno, config=None) -> dict:
    """Decide entre entregar, reescrever ou cair na mensagem de limitação."""
    avaliacao: regras.Criticidade = estado.get("criticidade", regras.NAO_CRITICO)
    rascunho = estado.get("rascunho", "")

    veredito = limites.validar(
        resposta=rascunho,
        ferramentas_usadas=estado.get("ferramentas_usadas", []),
        critico=avaliacao.critico,
    )

    if veredito.aprovada:
        return {"resposta": rascunho, "violacoes": []}

    revisao = estado.get("revisao", 0)
    if revisao < configuracao.MAX_REVISOES:
        return {"violacoes": veredito.violacoes, "revisao": revisao + 1}

    return {"resposta": limites.MENSAGEM_LIMITACAO, "violacoes": veredito.violacoes}


def limitacao(_estado: EstadoDoTurno, config=None) -> dict:
    """Saída segura única para qualquer falha de serviço no caminho."""
    return {"resposta": limites.MENSAGEM_LIMITACAO}


# --- roteamento ---------------------------------------------------------------


def _falhou(estado: EstadoDoTurno) -> bool:
    return bool(estado.get("codigo_erro"))


def rota_apos_coletar(estado: EstadoDoTurno) -> str:
    return "limitacao" if _falhou(estado) else "criticidade"


def rota_apos_criticidade(estado: EstadoDoTurno) -> str:
    if _falhou(estado):
        return "limitacao"

    avaliacao: regras.Criticidade = estado.get("criticidade", regras.NAO_CRITICO)
    # Alerta sem paciente identificado não teria destinatário no plantão.
    if avaliacao.critico and estado.get("id_paciente"):
        return "alerta"
    return "gerar"


def rota_apos_alerta(estado: EstadoDoTurno) -> str:
    return "limitacao" if _falhou(estado) else "gerar"


def rota_apos_gerar(estado: EstadoDoTurno) -> str:
    return "limitacao" if _falhou(estado) else "escalonamento"


def rota_apos_escalonamento(estado: EstadoDoTurno) -> str:
    return "limitacao" if _falhou(estado) else "validar"


def rota_apos_validar(estado: EstadoDoTurno) -> str:
    if _falhou(estado):
        return "limitacao"
    # Sem resposta definida, `validar` pediu reescrita.
    return END if estado.get("resposta") else "gerar"


# --- montagem -----------------------------------------------------------------


def montar_grafo(agente_roteador):
    """Monta o grafo do turno em volta do agente que faz as consultas.

    O agente entra como subgrafo, e não como chamada dentro de um nó, para que
    as atualizações dele apareçam no stream enquanto acontecem. É o que mantém a
    trilha de ferramentas da interface preenchendo em tempo real, em vez de
    surgir inteira quando a recuperação termina.
    """
    grafo = StateGraph(EstadoDoTurno)

    grafo.add_node("inicializar", auditado("inicializar", inicializar))
    grafo.add_node("identificar", auditado("identificar", identificar_paciente))
    grafo.add_node("recuperar", agente_roteador)
    grafo.add_node("coletar", auditado("coletar", coletar_recuperacao))
    grafo.add_node("criticidade", auditado("criticidade", avaliar_criticidade))
    grafo.add_node("alerta", auditado("alerta", alertar_equipe))
    grafo.add_node("gerar", auditado("gerar", gerar))
    grafo.add_node("escalonamento", auditado("escalonamento", escalonar))
    grafo.add_node("validar", auditado("validar", validar))
    grafo.add_node("limitacao", auditado("limitacao", limitacao))

    grafo.add_edge(START, "inicializar")
    grafo.add_edge("inicializar", "identificar")
    grafo.add_edge("identificar", "recuperar")
    grafo.add_edge("recuperar", "coletar")

    grafo.add_conditional_edges(
        "coletar",
        rota_apos_coletar,
        {"criticidade": "criticidade", "limitacao": "limitacao"},
    )
    grafo.add_conditional_edges(
        "criticidade",
        rota_apos_criticidade,
        {"alerta": "alerta", "gerar": "gerar", "limitacao": "limitacao"},
    )
    grafo.add_conditional_edges(
        "alerta", rota_apos_alerta, {"gerar": "gerar", "limitacao": "limitacao"}
    )
    grafo.add_conditional_edges(
        "gerar",
        rota_apos_gerar,
        {"escalonamento": "escalonamento", "limitacao": "limitacao"},
    )
    grafo.add_conditional_edges(
        "escalonamento",
        rota_apos_escalonamento,
        {"validar": "validar", "limitacao": "limitacao"},
    )
    grafo.add_conditional_edges(
        "validar", rota_apos_validar, {"gerar": "gerar", END: END}
    )
    grafo.add_edge("limitacao", END)

    return grafo.compile()
