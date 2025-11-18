# core/sla.py

import logging
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =========================
# TABELA PROFISSIONAL DE SLA PADRÃO
# =========================
# Ajuste esses valores conforme a política do HRA
SLA_PADRAO = {
    "adesao": 20,     # dias
    "arp": 30,        # dias
    "registro": 25,   # dias
    "outros": 15,     # fallback
}


# =========================
# FUNÇÕES DE APOIO
# =========================

def achar_coluna(df: pd.DataFrame, possiveis: Iterable[str]) -> str | None:
    """
    Procura uma coluna no DataFrame considerando variações de nome
    (diferença de acento, espaços, maiúsculas/minúsculas).
    """
    candidatos_normalizados = [p.lower().strip() for p in possiveis]
    for coluna in df.columns:
        if coluna.lower().strip() in candidatos_normalizados:
            return coluna
    return None


def detectar_tipo_simplificado(tipo_str: str) -> str:
    """
    Classifica o tipo da solicitação em categorias simplificadas
    para aplicação de SLA.
    """
    if not isinstance(tipo_str, str):
        return "outros"

    t = tipo_str.lower()

    # Exemplos – ajuste conforme os tipos reais da sua planilha
    if "adesão" in t or "adesao" in t:
        return "adesao"
    if "ata de registro" in t or "arp" in t:
        return "arp"
    if "registro" in t or "registro de preços" in t:
        return "registro"

    return "outros"


# =========================
# FUNÇÃO PRINCIPAL
# =========================

def aplicar_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica regras de SLA ao DataFrame:

    - tipo_simplificado: categoria do tipo da solicitação
    - sla_manual: dias informados manualmente (se existir coluna adequada)
    - sla_auto: SLA calculado automaticamente a partir do tipo
    - sla_final: se houver SLA manual, ele tem prioridade; senão, usa o automático
    - atrasado: True se lead_time > sla_final
    """
    df = df.copy()

    # 1) Tipo da solicitação -> tipo_simplificado
    col_tipo = achar_coluna(
        df,
        ["Tipo da solicitação", "Tipo da Solicitação", "Tipo Solicitação", "tipo_solicitacao"],
    )

    if col_tipo is not None:
        df["tipo_simplificado"] = df[col_tipo].apply(detectar_tipo_simplificado)
        logger.info(f"tipo_simplificado criado a partir de '{col_tipo}'.")
    else:
        df["tipo_simplificado"] = "outros"
        logger.warning(
            "Coluna de 'Tipo da solicitação' não encontrada; "
            "tipo_simplificado definido como 'outros' para todas as linhas."
        )

    # 2) SLA manual (se existir alguma coluna numérica de SLA)
    #    Você pode adaptar esses nomes à sua planilha
    col_sla_manual = achar_coluna(
        df,
        ["SLA manual", "sla_manual", "SLA", "Prazo SLA", "Prazo (dias)", "Status da Coluna M"],
    )

    if col_sla_manual is not None:
        df["sla_manual"] = pd.to_numeric(df[col_sla_manual], errors="coerce")
        logger.info(f"sla_manual criado a partir de '{col_sla_manual}'.")
    else:
        df["sla_manual"] = np.nan
        logger.info("Nenhuma coluna de SLA manual encontrada; sla_manual = NaN.")

    # 3) SLA automático pela regra padrão
    df["sla_auto"] = df["tipo_simplificado"].map(SLA_PADRAO).astype("float")

    # 4) SLA final – manual tem prioridade, se existir
    df["sla_final"] = df["sla_manual"].combine_first(df["sla_auto"])

    # 5) Indicador de atraso
    if "lead_time" in df.columns:
        df["atrasado"] = (df["lead_time"] > df["sla_final"]) & df["sla_final"].notna()
    else:
        df["atrasado"] = False
        logger.warning(
            "Coluna 'lead_time' não encontrada ao aplicar SLA; "
            "'atrasado' definido como False para todas as linhas."
        )

    return df
