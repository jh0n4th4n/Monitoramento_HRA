# core/indicadores.py

import pandas as pd
import logging
import yaml
from utils.logging_config import configurar_logging
from core.etl import achar_coluna

logger = configurar_logging()

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)


def _garantir_status_macro(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "status_macro" in df.columns:
        return df

    possiveis = ["Situação  do Processo", "Situação do Processo", "Situação Processo"]
    col_status = achar_coluna(df, possiveis)

    if col_status is not None:
        s = df[col_status].astype(str).str.strip().str.lower()

        def map_status(txt: str) -> str:
            if "cancel" in txt:
                return "Cancelado"
            if "indefer" in txt or "defer" in txt or "finaliz" in txt or "conclu" in txt:
                return "Concluído"
            if "andamento" in txt or "analise" in txt or "análise" in txt or "pendente" in txt:
                return "Em andamento"
            return "Outro"

        df["status_macro"] = s.apply(map_status)
        logger.info(f"status_macro criado a partir de '{col_status}'.")
    else:
        df["status_macro"] = "Indefinido"
        logger.warning("Nenhuma coluna de status encontrada; status_macro = 'Indefinido'.")

    return df


def _garantir_atrasado(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "atrasado" not in df.columns:
        df["atrasado"] = False
        logger.warning("Coluna 'atrasado' não encontrada; criada como False.")
    return df


def calcular_kpis_executivos(df: pd.DataFrame) -> dict:
    try:
        df = _garantir_status_macro(df)
        df = _garantir_atrasado(df)

        total = len(df)
        concluido = len(df[df["status_macro"] == "Concluído"])
        atrasado = len(df[df["atrasado"]])
        cancelado = len(df[df["status_macro"] == "Cancelado"])

        kpis = {
            "Total Solicitações": total,
            "Concluídas": concluido,
            "Atrasadas": atrasado,
            "Canceladas": cancelado,
            "Taxa Conclusão (%)": round((concluido / total) * 100, 2) if total > 0 else 0,
            "Taxa Atraso (%)": round((atrasado / total) * 100, 2) if total > 0 else 0,
        }

        logger.info("KPIs executivos calculados.")
        return kpis
    except Exception:
        logger.error("Erro ao calcular KPIs.", exc_info=True)
        return {}


def calcular_kpis_avancados(df: pd.DataFrame) -> dict:
    """
    KPIs avançados: estatísticas de lead_time, volumes críticos etc.
    """
    try:
        total = len(df)
        if "lead_time" in df.columns and total > 0:
            lt = df["lead_time"]
            media = lt.mean()
            mediana = lt.median()
            p75 = lt.quantile(0.75)
            p90 = lt.quantile(0.90)
            p95 = lt.quantile(0.95)
        else:
            media = mediana = p75 = p90 = p95 = 0

        muito_antigo = df["muito_antigo"].sum() if "muito_antigo" in df.columns else 0
        sem_sei = (~df.get("tem_sei", False)).sum() if "tem_sei" in df.columns else 0
        sem_resp = 0
        possiveis_resp = ["Responsável", "Responsável Técnico", "Responsavel Tecnico"]
        col_resp = achar_coluna(df, possiveis_resp)
        if col_resp is not None:
            sem_resp = (df[col_resp].isna() | (df[col_resp].astype(str).str.strip() == "")).sum()

        kpis = {
            "lead_media": round(media, 1),
            "lead_mediana": round(mediana, 1),
            "lead_p75": int(p75),
            "lead_p90": int(p90),
            "lead_p95": int(p95),
            "qtd_muito_antigo": int(muito_antigo),
            "qtd_sem_sei": int(sem_sei),
            "qtd_sem_responsavel": int(sem_resp),
        }

        logger.info("KPIs avançados calculados.")
        return kpis
    except Exception:
        logger.error("Erro ao calcular KPIs avançados.", exc_info=True)
        return {}


def funil_operacional(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = _garantir_status_macro(df)
        funil = df["status_macro"].value_counts(dropna=False).reset_index()
        funil.columns = ["status_macro", "quantidade"]
        funil["percentual"] = (funil["quantidade"] / len(df) * 100).round(2) if len(df) > 0 else 0
        logger.info("Funil operacional calculado.")
        return funil
    except Exception:
        logger.error("Erro no funil operacional.", exc_info=True)
        return pd.DataFrame()


def produtividade_por_nucleo(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df = _garantir_status_macro(df)
        possiveis_nucleo = ["Núcleo Pertencente", "Núcleo", "Nucleo"]
        col_nucleo = achar_coluna(df, possiveis_nucleo)
        if col_nucleo is None:
            logger.warning("Nenhuma coluna de núcleo encontrada.")
            return pd.DataFrame()

        tabela = df.groupby(col_nucleo)["status_macro"].value_counts().unstack(fill_value=0)
        if "Concluído" in tabela.columns:
            tabela["Conclusão (%)"] = (tabela["Concluído"] / tabela.sum(axis=1) * 100).round(2)
        else:
            tabela["Conclusão (%)"] = 0

        logger.info("Produtividade por núcleo calculada.")
        return tabela
    except Exception:
        logger.error("Erro ao calcular produtividade por núcleo.", exc_info=True)
        return pd.DataFrame()


def top_processos_criticos(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    try:
        if "lead_time" not in df.columns:
            logger.warning("Sem coluna lead_time para processos críticos.")
            return pd.DataFrame()
        df_ord = df.sort_values("lead_time", ascending=False).head(n)
        logger.info("Top processos críticos calculados.")
        return df_ord
    except Exception:
        logger.error("Erro ao calcular processos críticos.", exc_info=True)
        return pd.DataFrame()


def tabela_taxa_atraso_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """
    Retorna tabela com total, atrasadas e taxa de atraso por grupo (órgão, núcleo, etc).
    """
    if coluna not in df.columns:
        return pd.DataFrame()

    df = _garantir_atrasado(df)
    total = df.groupby(coluna).size()
    atrasadas = df[df["atrasado"]].groupby(coluna).size()
    tabela = pd.concat([total, atrasadas], axis=1).fillna(0)
    tabela.columns = ["Total", "Atrasadas"]
    tabela["Taxa Atraso (%)"] = (tabela["Atrasadas"] / tabela["Total"] * 100).round(2)
    tabela = tabela.sort_values("Taxa Atraso (%)", ascending=False)
    return tabela.reset_index()


def tabela_leadtime_por(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """
    Estatísticas de lead_time por grupo.
    """
    if coluna not in df.columns or "lead_time" not in df.columns:
        return pd.DataFrame()

    agg = df.groupby(coluna)["lead_time"].agg(
        Total="count",
        Média="mean",
        Mediana="median",
        P75=lambda s: s.quantile(0.75),
        P90=lambda s: s.quantile(0.90),
    )
    agg["Média"] = agg["Média"].round(1)
    agg["Mediana"] = agg["Mediana"].round(1)
    agg["P75"] = agg["P75"].round(1)
    agg["P90"] = agg["P90"].round(1)
    return agg.reset_index()
