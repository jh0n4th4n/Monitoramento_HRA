# core/etl.py

import pandas as pd
import yaml
import logging
import yaml
from utils.logging_config import configurar_logging

logger = configurar_logging()

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)

CAMINHO_EXCEL = settings["geral"]["caminho_excel"]
DEFAULT_DATE = pd.to_datetime(settings["geral"]["default_date"])
SAVE_PARQUET = settings["geral"]["salvar_parquet"]
CAMINHO_PARQUET = settings["geral"]["caminho_parquet"]


def achar_coluna(df: pd.DataFrame, possiveis) -> str | None:
    """
    Procura uma coluna no DataFrame considerando variações de nome.
    Ex.: achar_coluna(df, ["Orgão", "Órgão"]) -> retorna o nome real encontrado.
    """
    candidatos_normalizados = [p.lower().strip() for p in possiveis]
    for coluna in df.columns:
        if coluna.lower().strip() in candidatos_normalizados:
            return coluna
    return None


def _criar_status_macro(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria a coluna status_macro a partir de 'Situação  do Processo' (ou similar).
    """
    possiveis_status = ["Situação  do Processo", "Situação do Processo", "Situação Processo"]
    col_status = achar_coluna(df, possiveis_status)

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
        logger.warning("Coluna de situação do processo não encontrada; status_macro = 'Indefinido'.")

    return df


def _criar_lead_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria a coluna lead_time (dias desde a data da solicitação até hoje).
    """
    possiveis_data_solic = ["Data da solicitação", "Data da Solicitação"]
    col_data_solic = achar_coluna(df, possiveis_data_solic)

    if col_data_solic is not None:
        df[col_data_solic] = pd.to_datetime(df[col_data_solic], errors="coerce").fillna(DEFAULT_DATE)
        hoje = pd.Timestamp("today").normalize()
        df["lead_time"] = (hoje - df[col_data_solic]).dt.days.astype(int)
        logger.info(f"lead_time calculado a partir de '{col_data_solic}'.")
    else:
        df["lead_time"] = 0
        logger.warning("Coluna de data da solicitação não encontrada; lead_time definido como 0.")

    return df


def _enriquecer_campos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Cria variáveis derivadas:
    - tem_sei
    - tem_andamento_sei
    - complexidade_aprox (Baixa / Média / Alta)
    """
    # SEI
    col_sei = achar_coluna(df, ["SEI"])
    if col_sei is not None:
        df[col_sei] = df[col_sei].astype(str)
        df["tem_sei"] = df[col_sei].astype(str).str.strip().str.len() > 0
        logger.info(f"Flag tem_sei criada a partir de '{col_sei}'.")
    else:
        df["tem_sei"] = False
        logger.info("Coluna SEI não encontrada; tem_sei = False.")

    # Andamento SEI
    col_and_sei = achar_coluna(df, ["Andamento SEI"])
    if col_and_sei is not None:
        df["tem_andamento_sei"] = df[col_and_sei].astype(str).str.strip().str.len() > 0
    else:
        df["tem_andamento_sei"] = False

    # Complexidade aproximada pela 'Tipo da solicitação'
    possiveis_tipo = ["Tipo da solicitação", "Tipo da Solicitação", "Tipo Solicitação"]
    col_tipo = achar_coluna(df, possiveis_tipo)

    def classificar_complexidade(tipo: str) -> str:
        t = str(tipo).lower()
        if any(x in t for x in ["dispensa", "adesão", "adesao", "ata de registro", "renovação", "renovacao"]):
            return "Baixa"
        if any(x in t for x in ["pregão", "pregao", "concorrência", "concorrencia", "tomada de preços"]):
            return "Alta"
        if t.strip() == "" or t == "nan":
            return "Indefinida"
        return "Média"

    if col_tipo is not None:
        df["complexidade_aprox"] = df[col_tipo].apply(classificar_complexidade)
        logger.info(f"complexidade_aprox criada a partir de '{col_tipo}'.")
    else:
        df["complexidade_aprox"] = "Indefinida"
        logger.info("Coluna de tipo da solicitação não encontrada; complexidade_aprox = 'Indefinida'.")

    return df


def preparar_base() -> pd.DataFrame:
    """
    Carrega e trata a base conforme as colunas reais da planilha.
    """
    try:
        logger.info(f"Lendo base de dados: {CAMINHO_EXCEL}")
        df = pd.read_excel(CAMINHO_EXCEL)
        df.columns = df.columns.str.strip()
        logger.info(f"Colunas encontradas: {list(df.columns)}")
    except Exception as e:
        logger.error("Erro ao carregar Excel", exc_info=True)
        raise e

    df = _criar_lead_time(df)
    df = _criar_status_macro(df)
    df = _enriquecer_campos(df)

    logger.info("Base tratada e enriquecida com sucesso.")
    return df


def salvar_base_parquet(df: pd.DataFrame) -> None:
    """
    Salva a base em Parquet (cache), tratando problemas de tipo.
    """
    if not SAVE_PARQUET:
        logger.info("Salvamento em Parquet desativado.")
        return

    df_clean = df.copy()
    col_sei = achar_coluna(df_clean, ["SEI"])
    if col_sei is not None:
        df_clean[col_sei] = df_clean[col_sei].astype(str)

    try:
        df_clean.to_parquet(CAMINHO_PARQUET, index=False)
        logger.info(f"Base salva como Parquet em: {CAMINHO_PARQUET}")
    except Exception:
        logger.error("Erro ao salvar Parquet; seguindo sem cache.", exc_info=True)


def carregar_base_tratada() -> pd.DataFrame:
    """
    Carrega a base:
    - Se Parquet existir e estiver ok, usa Parquet.
    - Senão, roda ETL completo (Excel -> tratamento -> Parquet).
    """
    if SAVE_PARQUET:
        try:
            df = pd.read_parquet(CAMINHO_PARQUET)
            logger.info(f"Base carregada de Parquet: {CAMINHO_PARQUET}")
            return df
        except Exception:
            logger.warning("Parquet não encontrado ou inválido; rodando ETL completo.")

    df = preparar_base()
    salvar_base_parquet(df)
    return df
