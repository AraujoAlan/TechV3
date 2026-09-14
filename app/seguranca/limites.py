"""Verificação dos limites de atuação, para a auditoria.

A fase pede limites que evitem "sugestões impróprias, ex.: nunca prescrever
diretamente, sem validação humana". O limite existe e é defendido onde importa:

1. **No treino.** O `SYSTEM_ASSISTENTE` estava em toda linha do dataset, então a
   fronteira virou comportamento aprendido, não instrução contornável.
2. **No prompt.** O mesmo texto volta na inferência.
3. **Aqui.** As duas primeiras são probabilísticas; esta lê o que saiu e deixa
   registro.

O que este módulo **não** faz é acrescentar aviso à resposta. O leitor é o
médico — ele *é* a validação humana. Encerrar toda resposta com "valide com o
profissional responsável" seria endereçar o disclaimer a quem já é o
destinatário dele, e ruído repetido ensina a ignorar o aviso justamente nas
respostas em que ele contaria.

São duas funções, com poderes diferentes de propósito.

`verificar` **marca e não bloqueia**. É a que olha dose e modo verbal. Um
assistente que apaga o próprio texto por suspeita de uma regex falha justamente
nas respostas mais úteis, que são as que citam dose — e o destinatário aqui é
médico, para quem dose é informação, não risco. O que ela produz vai para
`logs/auditoria.jsonl`: se uma conduta for questionada depois, dá para achar
toda resposta que citou dose.

`validar` **bloqueia**, e só em dois casos, ambos verificáveis sem julgar o
conteúdo clínico:

- **caso crítico sem escalonamento.** O nó `escalonamento` já anexa o aviso; esta
  checagem é a rede embaixo dele. Se alguém mudar aquele nó e a rede não
  existisse, casos críticos sairiam sem orientação de acionar a equipe.
- **protocolo citado sem consulta.** É o caso que mais importa num sistema
  médico-a-médico: a resposta se apoia numa fonte que ninguém abriu. Aqui não é
  questão de tom, é de procedência — o médico pode agir sobre um protocolo que
  não existe.

O que ficou de fora do bloqueio foi deliberado. Exigir marcador de citação
`[S1]` no texto, como um validador genérico faria, reprovaria toda resposta
deste sistema: o redator é fine-tunado sem marcadores, e o system prompt é o do
treino. A procedência do turno é garantida pelo evento `sources`, que sai do
artefato da ferramenta — dado de código, não texto de modelo.
"""

import re
from dataclasses import dataclass, field

# O aviso que o nó `escalonamento` anexa, e o padrão que `validar` usa para
# conferir que ele está lá. Os dois moram juntos porque, separados, uma mudança
# de redação no aviso passaria a reprovar toda resposta crítica.
AVISO_ESCALONAMENTO = (
    "Este caso atende a critério de acionamento da equipe assistencial — "
    "avalie contato imediato com o plantão responsável."
)

PADRAO_ESCALONAMENTO = re.compile(
    r"acionamento da equipe|acionar a equipe|plantão|escalon|avaliação humana",
    re.IGNORECASE,
)

# Resposta que o grafo devolve quando não consegue sustentar o que escreveu.
# Escrita para médico: não manda "procurar um profissional de saúde", porque
# quem está lendo é o profissional de saúde.
MENSAGEM_LIMITACAO = (
    "Não consegui sustentar uma resposta com as fontes consultadas neste turno. "
    "Consulte o prontuário e o protocolo institucional diretamente antes de decidir."
)

# Dose explícita: "500 mg", "1,5 g", "10 UI", "2 comprimidos".
PADRAO_DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|l|ui|u|comprimidos?|c[áa]psulas?|gotas?)"
    r"(?:\s*/\s*(?:kg|dia|h|hora))?\b",
    re.IGNORECASE,
)

# Verbo em modo de determinação, e não de sugestão.
PADRAO_DETERMINACAO = re.compile(
    r"\b(prescrev[oa]|prescreva|receit[oe]|administre|inicie|suspenda)\b",
    re.IGNORECASE,
)

# Resposta que se apoia em protocolo institucional.
PADRAO_PROTOCOLO = re.compile(r"\bprotocolos?\s+(?:interno|institucional|do hospital|daqui)",
                              re.IGNORECASE)

FERRAMENTAS_DE_PROTOCOLO = {"consultar_protocolo", "listar_protocolos"}


def verificar(resposta: str, ferramentas_usadas: list[str]) -> list[str]:
    """Devolve os marcadores de auditoria encontrados no turno.

    Lista vazia não quer dizer resposta clinicamente correta: esta função olha
    forma, não conteúdo.

    Args:
        resposta: o texto gerado pelo redator.
        ferramentas_usadas: nomes das tools chamadas neste turno.
    """
    alertas: list[str] = []

    if PADRAO_DOSE.search(resposta):
        alertas.append("citou_dose")

    if PADRAO_DETERMINACAO.search(resposta):
        alertas.append("conduta_em_modo_determinacao")

    # O caso que mais importa num sistema médico-a-médico: a resposta apoiada
    # numa fonte que ninguém consultou. Aqui não é questão de tom, é de
    # procedência — o médico pode agir sobre um protocolo que não existe.
    if PADRAO_PROTOCOLO.search(resposta) and not (
        FERRAMENTAS_DE_PROTOCOLO & set(ferramentas_usadas)
    ):
        alertas.append("citou_protocolo_sem_consultar")

    return alertas


@dataclass(frozen=True)
class Validacao:
    """O veredito sobre uma resposta pronta."""

    aprovada: bool
    violacoes: list[str] = field(default_factory=list)


def validar(
    resposta: str, ferramentas_usadas: list[str], critico: bool
) -> Validacao:
    """Decide se a resposta pode ir ao médico como está.

    Reprovar aqui não descarta a resposta de imediato: o grafo tenta reescrevê-la
    enquanto houver orçamento de revisão, e só cai na mensagem de limitação
    quando o orçamento acaba. As violações viajam de volta ao redator, para que
    a segunda tentativa saiba o que corrigir.

    Args:
        resposta: o rascunho gerado no turno.
        ferramentas_usadas: nomes das tools chamadas neste turno.
        critico: se a avaliação determinística classificou o caso como crítico.
    """
    violacoes: list[str] = []

    if critico and not PADRAO_ESCALONAMENTO.search(resposta):
        violacoes.append(
            "Caso classificado como crítico, mas a resposta não orienta "
            "acionar a equipe."
        )

    if PADRAO_PROTOCOLO.search(resposta) and not (
        FERRAMENTAS_DE_PROTOCOLO & set(ferramentas_usadas)
    ):
        violacoes.append(
            "A resposta invoca protocolo institucional sem que nenhum "
            "protocolo tenha sido consultado neste turno."
        )

    # Resposta vazia é falha de geração, não de conteúdo — mas deixá-la passar
    # entregaria uma bolha em branco ao médico.
    if not resposta.strip():
        violacoes.append("O redator não produziu texto.")

    return Validacao(aprovada=not violacoes, violacoes=violacoes)
