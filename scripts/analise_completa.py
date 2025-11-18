# scripts/analise_completa.py

"""
Script de análise completa da base de solicitações.

Uso:
    python scripts/analise_completa.py

Requisitos:
    - settings.yaml corretamente configurado com o caminho do Excel
    - módulos core.etl e core.analises disponíveis
"""

from core.etl import carregar_base_tratada
from core.analises import (
    resumo_estrutura,
    missing_por_coluna,
    estatisticas_numericas,
    estatisticas_categoricas,
    matriz_correlacao,
    analise_lead_time,
    analise_temporal,
    analise_por_dimensao,
    exportar_relatorio_excel,
)
from utils.logging_config import configurar_logging

logger = configurar_logging()


def main():
    logger.info("🚀 Iniciando análise completa da base...")

    # Carrega a mesma base usada pelo dashboard
    df = carregar_base_tratada()
    logger.info(f"Base carregada com {len(df)} linhas e {len(df.columns)} colunas.")

    # Análises principais (também impressas no console em forma resumida)
    resumo = resumo_estrutura(df)
    miss = missing_por_coluna(df)
    num = estatisticas_numericas(df)
    cat = estatisticas_categoricas(df)
    corr = matriz_correlacao(df)
    lead = analise_lead_time(df)
    tempo = analise_temporal(df)
    dims = analise_por_dimensao(df)

    logger.info("=== RESUMO ESTRUTURA ===")
    logger.info("\n" + resumo.to_string(max_rows=20))

    logger.info("=== MISSING POR COLUNA (top 20) ===")
    logger.info("\n" + miss.head(20).to_string(index=False))

    if not num.empty:
        logger.info("=== ESTATÍSTICAS NUMÉRICAS ===")
        logger.info("\n" + num.to_string())

    if not cat.empty:
        logger.info("=== DISTRIBUIÇÃO CATEGÓRICAS (amostra) ===")
        logger.info("\n" + cat.head(30).to_string(index=False))

    if not corr.empty:
        logger.info("=== MATRIZ DE CORRELAÇÃO (amostra) ===")
        logger.info("\n" + corr.to_string())

    # Exporta relatório completo para Excel
    exportar_relatorio_excel(df, caminho_saida="output/relatorio_analise.xlsx")
    logger.info("✅ Análise completa finalizada.")


if __name__ == "__main__":
    main()
