"""Os limites de atuação: o que é marcado e o que é barrado.

A separação entre as duas funções é a decisão de projeto mais fácil de desfazer
sem querer, num refactor futuro. Por isso ela está fixada em teste: `verificar`
observa e registra, `validar` barra — e a lista do que cada uma alcança é curta
e explícita de propósito.
"""

from app.seguranca import limites

RESPOSTA_COM_DOSE = "Sugiro considerar sulfato de magnésio 4 g em ataque."


# --- verificar: marca para a auditoria, nunca bloqueia -------------------------


def test_marca_citacao_de_dose():
    assert "citou_dose" in limites.verificar(RESPOSTA_COM_DOSE, [])


def test_marca_conduta_em_modo_de_determinacao():
    alertas = limites.verificar("Prescreva o esquema padrão.", [])

    assert "conduta_em_modo_determinacao" in alertas


def test_marca_protocolo_citado_sem_consulta():
    alertas = limites.verificar("Conforme o protocolo interno, proceda.", [])

    assert "citou_protocolo_sem_consultar" in alertas


def test_nao_marca_protocolo_quando_houve_consulta():
    alertas = limites.verificar(
        "Conforme o protocolo interno, proceda.", ["consultar_protocolo"]
    )

    assert "citou_protocolo_sem_consultar" not in alertas


def test_resposta_comum_nao_gera_marcacao():
    assert limites.verificar("Quadro estável, manter observação.", []) == []


# --- validar: barra, e só nos casos verificáveis ------------------------------


def test_dose_nao_barra_a_resposta():
    # A decisão está documentada no módulo: o destinatário é médico, para quem
    # dose é informação. Barrar aqui falharia justamente nas respostas mais
    # úteis. A citação continua indo para a auditoria via `verificar`.
    assert limites.validar(RESPOSTA_COM_DOSE, [], critico=False).aprovada


def test_caso_critico_sem_escalonamento_e_barrado():
    veredito = limites.validar("Quadro estável.", [], critico=True)

    assert not veredito.aprovada
    assert "crítico" in veredito.violacoes[0]


def test_caso_critico_com_escalonamento_passa():
    veredito = limites.validar(
        f"Quadro grave. {limites.AVISO_ESCALONAMENTO}", [], critico=True
    )

    assert veredito.aprovada


def test_o_aviso_do_grafo_satisfaz_o_proprio_validador():
    # Os dois vivem no mesmo módulo exatamente para não divergirem: se alguém
    # reescrever o aviso sem ajustar o padrão, toda resposta crítica passaria a
    # ser reprovada em laço até cair na mensagem de limitação.
    assert limites.PADRAO_ESCALONAMENTO.search(limites.AVISO_ESCALONAMENTO)


def test_protocolo_sem_consulta_e_barrado():
    veredito = limites.validar(
        "Conforme o protocolo institucional, conduza assim.", [], critico=False
    )

    assert not veredito.aprovada


def test_protocolo_com_consulta_passa():
    veredito = limites.validar(
        "Conforme o protocolo institucional, conduza assim.",
        ["consultar_protocolo"],
        critico=False,
    )

    assert veredito.aprovada


def test_resposta_vazia_e_barrada():
    assert not limites.validar("   ", [], critico=False).aprovada


def test_citacao_numerada_nao_e_exigida():
    # Um validador genérico exigiria marcador [S1]. O redator deste sistema é
    # fine-tunado sem marcadores, então exigir isso reprovaria todo turno.
    assert limites.validar(
        "Resposta sem nenhum marcador de fonte.", ["buscar_paciente"], critico=False
    ).aprovada
