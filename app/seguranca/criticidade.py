"""Avaliação determinística de criticidade do caso.

A fase pede que o assistente acione a equipe quando o caso exigir. O gatilho
mora aqui, e é código — nunca uma LLM decidindo. Um alerta disparado por
julgamento de modelo não é audível: ninguém consegue dizer depois por que ele
soou, ou por que não soou.

Cada regra devolve `codigo_regra` e `versao_regra`. Quando um alerta for
questionado, é isso que permite reconstruir qual regra disparou e em que versão
ela estava — e mudar um limiar sem perder o histórico do limiar anterior.

**Por que as regras olham CID-10, e não sinais vitais.** O plano original era
avaliar saturação, frequência cardíaca e temperatura. Ao conferir o parquet, os
vitais se mostraram ruído: só existem para PEDIATRIA (1.577 de 10.000 registros)
e foram sorteados em faixas normais estreitas — saturação entre 95 e 100,
temperatura entre 36,0 e 37,5. Nenhum limiar clínico real dispara neles, porque
nenhum paciente sintético está fora da faixa normal.

O que carrega sinal de verdade é o `diagnostico_principal`, que veio do SIH/SUS
em CID-10 e não foi sorteado, e os rótulos explícitos que o gerador produziu
(`risco_gestacional`, `sangramento`, `dor_pelvica`). As regras abaixo usam esses
campos, por especialidade, porque cada especialidade preenche colunas
diferentes.

A regra de vitais pediátricos (`MAT-PED-003`) fica no código mesmo sem disparar
neste dataset. Ela está clinicamente correta e é o que passaria a valer no dia
em que o banco receber medidas reais; removê-la esconderia a lacuna em vez de
registrá-la.

**O que deliberadamente não é regra.** `desfecho == 'Óbito'` marca 2.038
registros, e seria o gatilho mais fácil de escrever. Mas desfecho é história
encerrada, não situação em curso: alertar a equipe de plantão sobre um óbito já
registrado é ruído que ensina a ignorar o alerta.
"""

from dataclasses import dataclass

import pandas as pd

VERSAO_REGRAS = "v1"

# --- Obstetrícia --------------------------------------------------------------
# Pré-eclâmpsia grave e eclâmpsia (O14, O15) e hemorragia pós-parto (O72) são as
# emergências que os protocolos internos mandam escalar na hora.
CID_EMERGENCIA_OBSTETRICA = {"O14", "O15"}
CID_HEMORRAGIA = {"O72"}

# --- Pediatria ----------------------------------------------------------------
CID_ASFIXIA_PERINATAL = {"P20", "P21"}
CID_INFECCAO_NEONATAL = {"P36", "P39"}

# Limiares de lactente. Ver a nota do módulo: corretos, mas inertes sobre os
# dados sintéticos atuais.
SATURACAO_MINIMA = 92
FREQUENCIA_RESPIRATORIA_MAXIMA = 60


@dataclass(frozen=True)
class Criticidade:
    """O veredito de criticidade de um caso, com a regra que o produziu."""

    critico: bool
    codigo_regra: str | None = None
    motivo: str | None = None
    versao_regra: str = VERSAO_REGRAS

    def como_dicionario(self) -> dict:
        """Formato plano, para a linha de auditoria."""
        return {
            "critico": self.critico,
            "codigo_regra": self.codigo_regra,
            "motivo": self.motivo,
            "versao_regra": self.versao_regra,
        }


NAO_CRITICO = Criticidade(critico=False)


def _ausente(valor) -> bool:
    """O valor é nulo?

    O parquet traz `NaN` nas colunas da especialidade que não se aplica ao
    paciente — obstétricas num caso pediátrico, por exemplo — e as colunas de
    texto usam os tipos nuláveis do pandas. `pd.NA` não responde a comparação
    booleana, então o truque `valor != valor` que funciona para `float('nan')`
    estoura aqui. `pd.isna` cobre os dois.
    """
    if valor is None:
        return True
    try:
        return bool(pd.isna(valor))
    except (TypeError, ValueError):
        return False


def _texto(paciente: dict, campo: str) -> str:
    """Lê um campo de texto do registro, tolerando nulo do pandas."""
    valor = paciente.get(campo)
    return "" if _ausente(valor) else str(valor).strip()


def _numero(paciente: dict, campo: str) -> float | None:
    valor = paciente.get(campo)
    if _ausente(valor):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _prefixo_cid(paciente: dict) -> str:
    """Os três primeiros caracteres do CID, que é o nível dos protocolos."""
    return _texto(paciente, "diagnostico_principal")[:3].upper()


def _obstetricia(paciente: dict, cid: str) -> Criticidade | None:
    if cid in CID_EMERGENCIA_OBSTETRICA:
        return Criticidade(
            critico=True,
            codigo_regra="MAT-OBS-001",
            motivo=f"Emergência hipertensiva da gestação (CID {cid}).",
        )

    if cid in CID_HEMORRAGIA:
        return Criticidade(
            critico=True,
            codigo_regra="MAT-OBS-002",
            motivo=f"Hemorragia pós-parto (CID {cid}).",
        )

    if _texto(paciente, "risco_gestacional").lower() == "alto":
        return Criticidade(
            critico=True,
            codigo_regra="MAT-OBS-003",
            motivo="Gestação classificada como de alto risco no registro.",
        )

    return None


def _pediatria(paciente: dict, cid: str) -> Criticidade | None:
    if cid in CID_ASFIXIA_PERINATAL:
        return Criticidade(
            critico=True,
            codigo_regra="MAT-PED-001",
            motivo=f"Asfixia perinatal (CID {cid}).",
        )

    if cid in CID_INFECCAO_NEONATAL:
        return Criticidade(
            critico=True,
            codigo_regra="MAT-PED-002",
            motivo=f"Infecção específica do período neonatal (CID {cid}).",
        )

    saturacao = _numero(paciente, "saturacao")
    frequencia = _numero(paciente, "frequencia_respiratoria")

    if (saturacao is not None and saturacao < SATURACAO_MINIMA) or (
        frequencia is not None and frequencia > FREQUENCIA_RESPIRATORIA_MAXIMA
    ):
        return Criticidade(
            critico=True,
            codigo_regra="MAT-PED-003",
            motivo="Sinais vitais fora da faixa esperada para lactente.",
        )

    return None


def _ginecologia(paciente: dict, _cid: str) -> Criticidade | None:
    # Sangramento aumentado sozinho é achado comum; junto de dor intensa é o
    # par que os protocolos tratam como abdome agudo a investigar.
    if (
        _texto(paciente, "sangramento").lower() == "aumentado"
        and _texto(paciente, "dor_pelvica").lower() == "intensa"
    ):
        return Criticidade(
            critico=True,
            codigo_regra="MAT-GIN-001",
            motivo="Sangramento aumentado com dor pélvica intensa.",
        )

    return None


REGRAS_POR_ESPECIALIDADE = {
    "OBSTETRICIA": _obstetricia,
    "PEDIATRIA": _pediatria,
    "GINECOLOGIA": _ginecologia,
}


def avaliar(paciente: dict | None) -> Criticidade:
    """Classifica o caso de um paciente.

    Sem paciente identificado não há criticidade a avaliar: uma pergunta geral
    ("quais diagnósticos são mais frequentes?") não tem caso clínico em curso, e
    inventar criticidade a partir dela produziria alerta sem destinatário.

    Args:
        paciente: a linha de `pacientes_sinteticos` como dicionário, tal como
            `FerramentaConsultaSIH.buscar_paciente` devolve. `None` quando a
            pergunta não identificou paciente.
    """
    if not paciente:
        return NAO_CRITICO

    especialidade = _texto(paciente, "especialidade").upper()
    regra = REGRAS_POR_ESPECIALIDADE.get(especialidade)
    if regra is None:
        return NAO_CRITICO

    return regra(paciente, _prefixo_cid(paciente)) or NAO_CRITICO
