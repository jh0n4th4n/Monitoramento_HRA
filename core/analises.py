# core/analises.py

import os
import pandas as pd
import numpy as np
import logging

from utils.logging_config import configurar_logging
from core.etl import achar_coluna

logger = configurar_logging()


def resumo_estrutura(df: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for col in df.columns:
        serie = df[col]
        linhas.append({
            "coluna": col,
            "dtype": str(serie.dtype),
            "nao_nulos": int(serie.notna().sum()),
            "nulos": int(serie.isna().sum()),
            "unicos": int(serie.nunique()),
        })
    resumo = pd.DataFrame(linhas)
    logger.info("📋 Resumo de estrutura gerado.")
    return resumo


def missing_por_coluna(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula valores faltantes por coluna, considerando:
    - NaN
    - strings vazias ou só com espaço
    - literais 'nan' e 'None' em colunas texto
    """
    df2 = df.copy()

    for col in df2.columns:
        if df2[col].dtype == "object" or pd.api.types.is_string_dtype(df2[col]):
            df2[col] = (
                df2[col]
                .astype(str)
                .str.strip()
                .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            )

    total = len(df2)
    miss = df2.isna().sum().sort_values(ascending=False)
    perc = (miss / total * 100).round(2)
    tabela = pd.DataFrame({
        "faltantes": miss.astype(int),
        "% faltantes": perc
    })
    tabela.index.name = "coluna"
    tabela.reset_index(inplace=True)
    logger.info("📉 Tabela de missing (incluindo brancos) gerada.")
    return tabela


def estatisticas_numericas(df: pd.DataFrame) -> pd.DataFrame:
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) == 0:
        logger.warning("⚠️ Nenhuma coluna numérica encontrada para estatísticas.")
        return pd.DataFrame()
    desc = df[num_cols].describe().T
    logger.info("📊 Estatísticas numéricas calculadas.")
    return desc


def estatisticas_categoricas(df: pd.DataFrame, max_categorias: int = 20) -> pd.DataFrame:
    cat_cols = df.select_dtypes(include=["object", "category", "bool"]).columns
    linhas = []
    total = len(df)
    for col in cat_cols:
        vc = df[col].value_counts(dropna=False).head(max_categorias)
        for categoria, qtd in vc.items():
            linhas.append({
                "coluna": col,
                "categoria": str(categoria),
                "contagem": int(qtd),
                "percentual": round(qtd / total * 100, 2) if total > 0 else 0.0,
            })
    tabela = pd.DataFrame(linhas)
    logger.info("📦 Distribuição de categóricas gerada.")
    return tabela


def matriz_correlacao(df: pd.DataFrame) -> pd.DataFrame:
    num_cols = df.select_dtypes(include=[np.number]).columns
    if len(num_cols) < 2:
        logger.warning("⚠️ Colunas numéricas insuficientes para correlação.")
        return pd.DataFrame()
    corr = df[num_cols].corr()
    logger.info("🔗 Matriz de correlação gerada.")
    return corr


def analise_lead_time(df: pd.DataFrame) -> dict:
    resultados = {}
    if "lead_time" not in df.columns:
        logger.warning("⚠️ 'lead_time' não encontrado para análise específica.")
        return resultados

    serie = df["lead_time"]
    resultados["lead_time_resumo"] = serie.describe()

    if "status_macro" in df.columns:
        resultados["lead_time_por_status"] = df.groupby("status_macro")["lead_time"].describe()
    else:
        resultados["lead_time_por_status"] = pd.DataFrame()

    if "sla_categoria" in df.columns:
        resultados["lead_time_por_sla"] = df.groupby("sla_categoria")["lead_time"].describe()
    else:
        resultados["lead_time_por_sla"] = pd.DataFrame()

    if "risco_categoria" in df.columns:
        resultados["lead_time_por_risco"] = df.groupby("risco_categoria")["lead_time"].describe()
    else:
        resultados["lead_time_por_risco"] = pd.DataFrame()

    logger.info("⏱ Análises específicas de lead_time geradas.")
    return resultados


def analise_temporal(df: pd.DataFrame) -> dict:
    resultados = {}

    possiveis_data_entrada = ["Data da solicitação", "Data da Solicitação"]
    col_entrada = achar_coluna(df, possiveis_data_entrada)

    if col_entrada is not None:
        serie = pd.to_datetime(df[col_entrada], errors="coerce")
        resultados["entrada_por_ano_mes"] = (
            serie
            .dropna()
            .dt.to_period("M")
            .value_counts()
            .sort_index()
            .rename_axis("ano_mes")
            .to_frame("quantidade")
        )
    else:
        resultados["entrada_por_ano_mes"] = pd.DataFrame()

    logger.info("📆 Análise temporal gerada.")
    return resultados


def analise_por_dimensao(df: pd.DataFrame) -> dict:
    resultados = {}

    possiveis_orgao = ["Orgão", "Órgão", "Órgão/UG"]
    possiveis_nucleo = ["Núcleo Pertencente", "Núcleo", "Nucleo"]
    possiveis_resp = ["Responsável", "Responsável Técnico", "Responsavel Tecnico"]

    col_orgao = achar_coluna(df, possiveis_orgao)
    col_nucleo = achar_coluna(df, possiveis_nucleo)
    col_resp = achar_coluna(df, possiveis_resp)

    if col_orgao is not None:
        resultados["contagem_por_orgao"] = (
            df[col_orgao].value_counts().rename_axis(col_orgao).to_frame("quantidade")
        )
    else:
        resultados["contagem_por_orgao"] = pd.DataFrame()

    if col_nucleo is not None:
        resultados["contagem_por_nucleo"] = (
            df[col_nucleo].value_counts().rename_axis(col_nucleo).to_frame("quantidade")
        )
    else:
        resultados["contagem_por_nucleo"] = pd.DataFrame()

    if col_resp is not None:
        resultados["contagem_por_responsavel"] = (
            df[col_resp].value_counts().rename_axis(col_resp).to_frame("quantidade")
        )
    else:
        resultados["contagem_por_responsavel"] = pd.DataFrame()

    logger.info("🏛 Análises por dimensões geradas.")
    return resultados


def exportar_relatorio_excel(
    df: pd.DataFrame,
    caminho_saida: str = "output/relatorio_analise.xlsx"
) -> None:
    """
    Gera um arquivo Excel com várias abas de análise.
    """
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)

    resumo = resumo_estrutura(df)
    miss = missing_por_coluna(df)
    num = estatisticas_numericas(df)
    cat = estatisticas_categoricas(df)
    corr = matriz_correlacao(df)
    lead = analise_lead_time(df)
    tempo = analise_temporal(df)
    dims = analise_por_dimensao(df)

    # distribuições avançadas
    dist_faixa_lead = df["faixa_lead_time"].value_counts().rename_axis("faixa_lead_time").to_frame("quantidade") if "faixa_lead_time" in df.columns else pd.DataFrame()
    dist_dim_risco = df["risco_dimensao_principal"].value_counts().rename_axis("dimensao_risco").to_frame("quantidade") if "risco_dimensao_principal" in df.columns else pd.DataFrame()

    with pd.ExcelWriter(caminho_saida, engine="xlsxwriter") as writer:
        resumo.to_excel(writer, sheet_name="Estrutura", index=False)
        miss.to_excel(writer, sheet_name="Missing", index=False)
        if not num.empty:
            num.to_excel(writer, sheet_name="Numéricas", index=True)
        if not cat.empty:
            cat.to_excel(writer, sheet_name="Categóricas", index=False)
        if not corr.empty:
            corr.to_excel(writer, sheet_name="Correlação", index=True)

        # Lead time
        if "lead_time_resumo" in lead:
            pd.DataFrame(lead["lead_time_resumo"]).to_excel(writer, sheet_name="LeadTime_Resumo")
        if "lead_time_por_status" in lead and not lead["lead_time_por_status"].empty:
            lead["lead_time_por_status"].to_excel(writer, sheet_name="LeadTime_Status")
        if "lead_time_por_sla" in lead and not lead["lead_time_por_sla"].empty:
            lead["lead_time_por_sla"].to_excel(writer, sheet_name="LeadTime_SLA")
        if "lead_time_por_risco" in lead and not lead["lead_time_por_risco"].empty:
            lead["lead_time_por_risco"].to_excel(writer, sheet_name="LeadTime_Risco")

        # Temporal
        if not tempo["entrada_por_ano_mes"].empty:
            tempo["entrada_por_ano_mes"].to_excel(writer, sheet_name="Entrada_AnoMes")

        # Dimensões
        if not dims["contagem_por_orgao"].empty:
            dims["contagem_por_orgao"].to_excel(writer, sheet_name="Por_Orgao")
        if not dims["contagem_por_nucleo"].empty:
            dims["contagem_por_nucleo"].to_excel(writer, sheet_name="Por_Nucleo")
        if not dims["contagem_por_responsavel"].empty:
            dims["contagem_por_responsavel"].to_excel(writer, sheet_name="Por_Responsavel")

        # Distribuições extras
        if not dist_faixa_lead.empty:
            dist_faixa_lead.to_excel(writer, sheet_name="Faixas_LeadTime")
        if not dist_dim_risco.empty:
            dist_dim_risco.to_excel(writer, sheet_name="Risco_Dimensoes")

    logger.info(f"📑 Relatório de análise exportado para: {caminho_saida}")
