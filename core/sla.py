# core/sla.py

import pandas as pd
import logging
import yaml
from utils.logging_config import configurar_logging
from core.etl import achar_coluna

logger = configurar_logging()

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)

SLA_PADRAO = settings["sla"]["sla_padrao"]
MULTIPLIERS = settings["sla"]["multipliers"]
LIMITE_ATRASO_SEVERO = settings["sla"]["limite_atraso_severo"]


def _criar_faixas_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria a coluna faixa_lead_time (buckets de aging) e muito_antigo.
    """
    if "lead_time" not in df.columns:
        df["lead_time"] = 0

    bins = [-1, 30, 60, 90, 180, 365, 10_000]
    labels = ["0–30 dias", "31–60 dias", "61–90 dias", "91–180 dias", "181–365 dias", ">365 dias"]
    df["faixa_lead_time"] = pd.cut(df["lead_time"], bins=bins, labels=labels)
    df["muito_antigo"] = df["lead_time"] > 365

    return df


def aplicar_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica regras de SLA:
    - Usa 'Tipo da solicitação' (ou similar) se existir.
    - Usa lead_time já criado no ETL (dias desde a abertura).
    - Cria margem_sla, faixa_lead_time e muito_antigo.
    """
    df = df.copy()
    try:
        df["sla_base"] = SLA_PADRAO

        possiveis_tipo = ["Tipo da solicitação", "Tipo da Solicitação", "Tipo Solicitação"]
        col_tipo = achar_coluna(df, possiveis_tipo)

        if col_tipo is not None:
            def _calc_sla(tipo):
                chave = str(tipo).strip()
                return MULTIPLIERS.get(chave, 1) * SLA_PADRAO

            df["sla_final"] = df[col_tipo].apply(_calc_sla)
            logger.info(f"SLA calculado com base na coluna '{col_tipo}'.")
        else:
            df["sla_final"] = SLA_PADRAO
            logger.warning("Coluna de tipo da solicitação não encontrada; usando SLA padrão para todos.")

        if "lead_time" not in df.columns:
            df["lead_time"] = 0
            logger.warning("Coluna 'lead_time' não encontrada; criada com zeros.")

        # Flags de atraso
        df["atrasado"] = df["lead_time"] > df["sla_final"]
        df["atraso_severo"] = df["lead_time"] > LIMITE_ATRASO_SEVERO

        # Margem: dias até estourar o SLA (negativo = está atrasado)
        df["margem_sla"] = (df["sla_final"] - df["lead_time"]).astype(int)

        # Categoria amigável (mantida para compatibilidade)
        df["sla_categoria"] = "Dentro do prazo"
        df.loc[df["atrasado"], "sla_categoria"] = "Atrasado"
        df.loc[df["atraso_severo"], "sla_categoria"] = "Atraso Severo"

        # Faixas de aging
        df = _criar_faixas_lead_time(df)

        logger.info("Regras de SLA e faixas de lead_time aplicadas com sucesso.")
        return df
    except Exception:
        logger.error("Erro ao aplicar SLA.", exc_info=True)

        if "atrasado" not in df.columns:
            df["atrasado"] = False
        if "atraso_severo" not in df.columns:
            df["atraso_severo"] = False
        if "sla_categoria" not in df.columns:
            df["sla_categoria"] = "Indefinido"
        if "faixa_lead_time" not in df.columns:
            df["faixa_lead_time"] = "Indefinida"
        if "muito_antigo" not in df.columns:
            df["muito_antigo"] = False
        if "margem_sla" not in df.columns:
            df["margem_sla"] = 0

        return df
