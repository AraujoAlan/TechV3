"""As regras que decidem se a equipe é acionada.

O que se testa aqui é o gatilho do alerta. Ele precisa ser previsível a ponto de
alguém reconstruir, meses depois, por que o plantão foi chamado num caso e não
em outro — daí cada teste checar também o `codigo_regra`, e não só o booleano.
"""

import pandas as pd
import pytest

from app.seguranca import criticidade


def paciente(**campos) -> dict:
    """Um registro mínimo, com só o que a regra sob teste precisa."""
    base = {"especialidade": "OBSTETRICIA", "diagnostico_principal": "O80"}
    return {**base, **campos}


# --- obstetrícia --------------------------------------------------------------


@pytest.mark.parametrize("cid", ["O14", "O140", "O15"])
def test_emergencia_hipertensiva_e_critica(cid):
    resultado = criticidade.avaliar(paciente(diagnostico_principal=cid))

    assert resultado.critico
    assert resultado.codigo_regra == "MAT-OBS-001"


def test_hemorragia_pos_parto_e_critica():
    resultado = criticidade.avaliar(paciente(diagnostico_principal="O72"))

    assert resultado.critico
    assert resultado.codigo_regra == "MAT-OBS-002"


def test_alto_risco_gestacional_e_critico():
    resultado = criticidade.avaliar(paciente(risco_gestacional="Alto"))

    assert resultado.critico
    assert resultado.codigo_regra == "MAT-OBS-003"


def test_risco_baixo_nao_e_critico():
    assert not criticidade.avaliar(paciente(risco_gestacional="Baixo")).critico


# --- pediatria ----------------------------------------------------------------


def test_asfixia_perinatal_e_critica():
    resultado = criticidade.avaliar(
        paciente(especialidade="PEDIATRIA", diagnostico_principal="P210")
    )

    assert resultado.codigo_regra == "MAT-PED-001"


def test_ictericia_neonatal_nao_e_critica_por_si():
    # P59 é o diagnóstico mais comum da pediatria no banco (675 casos). Se ele
    # disparasse alerta, o plantão receberia ruído em quase metade dos casos
    # pediátricos e aprenderia a ignorar o aviso.
    resultado = criticidade.avaliar(
        paciente(especialidade="PEDIATRIA", diagnostico_principal="P59")
    )

    assert not resultado.critico


def test_sinais_vitais_fora_da_faixa_sao_criticos():
    resultado = criticidade.avaliar(
        paciente(
            especialidade="PEDIATRIA", diagnostico_principal="P59", saturacao=88
        )
    )

    assert resultado.codigo_regra == "MAT-PED-003"


# --- ginecologia --------------------------------------------------------------


def test_sangramento_com_dor_intensa_e_critico():
    resultado = criticidade.avaliar(
        paciente(
            especialidade="GINECOLOGIA",
            diagnostico_principal="N93",
            sangramento="Aumentado",
            dor_pelvica="Intensa",
        )
    )

    assert resultado.codigo_regra == "MAT-GIN-001"


def test_sangramento_isolado_nao_e_critico():
    resultado = criticidade.avaliar(
        paciente(
            especialidade="GINECOLOGIA",
            diagnostico_principal="N93",
            sangramento="Aumentado",
            dor_pelvica="Leve",
        )
    )

    assert not resultado.critico


# --- bordas -------------------------------------------------------------------


def test_sem_paciente_nao_ha_criticidade():
    # Pergunta geral ("quais diagnósticos são mais frequentes?") não tem caso
    # clínico em curso, e um alerta sem paciente não teria destinatário.
    assert not criticidade.avaliar(None).critico


def test_campo_ausente_nao_quebra_a_regra():
    # O parquet traz NaN nas colunas da especialidade que não se aplica ao
    # paciente. A regra tem que atravessar isso sem estourar.
    resultado = criticidade.avaliar(
        paciente(risco_gestacional=pd.NA, sangramento=float("nan"))
    )

    assert not resultado.critico


def test_desfecho_obito_nao_dispara_alerta():
    # Desfecho é história encerrada. Ver a nota do módulo: alertar o plantão
    # sobre um óbito já registrado é ruído.
    assert not criticidade.avaliar(paciente(desfecho="Óbito")).critico


def test_regra_carrega_versao():
    resultado = criticidade.avaliar(paciente(risco_gestacional="Alto"))

    assert resultado.versao_regra == criticidade.VERSAO_REGRAS
    assert resultado.como_dicionario()["codigo_regra"] == "MAT-OBS-003"
