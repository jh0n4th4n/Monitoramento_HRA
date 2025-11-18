# core/risco.py

import pandas as pd
import logging
import yaml
from utils.logging_config import configurar_logging

logger = configurar_logging()

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)

PESOS = settings["risco"]["pesos"]
LIMITE_LEAD = settings["risco"]["limite_lead_time_extremo"]


def _serie_booleana(df: pd.DataFrame, default=False):
    return pd.Series([default] * len(df), index=df.index)


def calcular_risco(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula risco com base em:
    - atraso, cancelamento, lead_time extremo,
    - falha de SEI (vazio),
    - ausência de Responsável.
    E cria dimensões de risco (tempo, operacional, governança).
    """
    df = df.copy()
    try:
        df["risco_score"] = 0

        # Atraso
        if "atrasado" in df.columns:
            cond_atraso = df["atrasado"].fillna(False).astype(bool)
        else:
            cond_atraso = _serie_booleana(df, False)
            logger.warning("Coluna 'atrasado' não encontrada para risco.")
        df["risco_score"] += cond_atraso.astype(int) * PESOS.get("atraso", 0)

        # Cancelado
        if "status_macro" in df.columns:
            cond_cancelado = df["status_macro"].eq("Cancelado")
        else:
            cond_cancelado = _serie_booleana(df, False)
            logger.warning("Coluna 'status_macro' não encontrada para risco de cancelamento.")
        df["risco_score"] += cond_cancelado.astype(int) * PESOS.get("cancelado", 0)

        # Lead_time extremo
        if "lead_time" in df.columns:
            cond_lead_extremo = df["lead_time"].gt(LIMITE_LEAD)
        else:
            cond_lead_extremo = _serie_booleana(df, False)
            logger.warning("Coluna 'lead_time' não encontrada para risco de lead_time extremo.")
        df["risco_score"] += cond_lead_extremo.astype(int) * PESOS.get("lead_time_extremo", 0)

        # Falha de SEI (campo vazio)
        possiveis_colunas_sei = ["Andamento SEI", "SEI"]
        col_sei = next((c for c in possiveis_colunas_sei if c in df.columns), None)
        if col_sei is not None:
            cond_falha_sei = df[col_sei].astype(str).str.strip().str.len().eq(0)
        else:
            cond_falha_sei = _serie_booleana(df, False)
            logger.warning("Nenhuma coluna de SEI encontrada para risco.")
        df["risco_score"] += cond_falha_sei.astype(int) * PESOS.get("falha_sei", 0)

        # Sem responsável
        possiveis_resp = ["Responsável", "Responsável Técnico", "Responsavel Técnico", "Responsavel Tecnico"]
        col_resp = next((c for c in possiveis_resp if c in df.columns), None)
        if col_resp is not None:
            cond_sem_resp = df[col_resp].isna() | (df[col_resp].astype(str).str.strip() == "")
        else:
            cond_sem_resp = _serie_booleana(df, False)
            logger.warning("Coluna de responsável não encontrada para risco.")
        df["risco_score"] += cond_sem_resp.astype(int) * PESOS.get("sem_responsavel", 0)

        # Categoria de risco
        df["risco_categoria"] = pd.cut(
            df["risco_score"],
            bins=[-1, 20, 50, 1000],
            labels=["Baixo", "Moderado", "Alto"]
        )

        # Dimensões de risco
        df["risco_tempo_flag"] = cond_atraso | cond_lead_extremo
        df["risco_operacional_flag"] = cond_sem_resp | cond_falha_sei
        df["risco_governanca_flag"] = cond_cancelado

        def _dimensao_principal(row) -> str:
            dims = {
                "Tempo": row.get("risco_tempo_flag", False),
                "Operacional": row.get("risco_operacional_flag", False),
                "Governança": row.get("risco_governanca_flag", False),
            }
            ativos = [nome for nome, flag in dims.items() if flag]
            if len(ativos) == 0:
                return "Nenhum"
            if len(ativos) == 1:
                return ativos[0]
            return "Misto"

        df["risco_dimensao_principal"] = df.apply(_dimensao_principal, axis=1)

        logger.info("Risco calculado com sucesso com dimensões detalhadas.")
        return df
    except Exception:
        logger.error("Erro ao calcular risco.", exc_info=True)
        if "risco_score" not in df.columns:
            df["risco_score"] = 0
        if "risco_categoria" not in df.columns:
            df["risco_categoria"] = "Indefinido"
        if "risco_tempo_flag" not in df.columns:
            df["risco_tempo_flag"] = False
        if "risco_operacional_flag" not in df.columns:
            df["risco_operacional_flag"] = False
        if "risco_governanca_flag" not in df.columns:
            df["risco_governanca_flag"] = False
        if "risco_dimensao_principal" not in df.columns:
            df["risco_dimensao_principal"] = "Indefinido"
        return df
