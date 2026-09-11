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

Também não bloqueia nem reescreve. Um assistente que apaga o próprio texto por
suspeita de uma regex falha nas respostas mais úteis, que são as que citam dose.

O que ele faz é marcar o turno na auditoria. Se uma conduta for questionada
depois, dá para achar em `logs/auditoria.jsonl` toda resposta que citou dose, e
toda resposta que invocou protocolo sem ter consultado nenhum.
"""

import re

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
