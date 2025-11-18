# ui/dashboards.py

from typing import Dict, Optional, List, Tuple

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px  # paletas modernas

from core.indicadores import (
    calcular_kpis_executivos,
    calcular_kpis_avancados,
    funil_operacional,
    produtividade_por_nucleo,
    top_processos_criticos,
    tabela_leadtime_por,
)
from core.analises import missing_por_coluna
from core.etl import achar_coluna
from core.risco import calcular_risco
from ui.ui_components import (
    section_title,
    section_subtitle,
    card_kpi,
    mostrar_grafico_barras,
    mostrar_grafico_linha,
    mostrar_heatmap,
    mostrar_grafico_pizza,
)
from ai.llm_assistente import (
    gerar_relatorio_ia,
    gerar_checklist_ia,
    gerar_ata_reuniao_ia,
)



# =================== CONFIGURAÇÕES GERAIS ===================

TABS_CONFIG = [
    {"key": "geral", "label": "📊 Visão Geral"},
    {"key": "orgao", "label": "🏛 Órgão & UG"},
    {"key": "nucleo", "label": "👥 Núcleo & Responsável"},
    {"key": "sla", "label": "⏱ SLA & Lead Time"},
    {"key": "risco", "label": "⚠️ Risco"},
    {"key": "dados", "label": "📂 Dados Filtrados"},
    {"key": "ia", "label": "🤖 Assistente IA"},
]


# =================== CACHES DE CÁLCULOS PESADOS ===================

@st.cache_data
def kpis_executivos_cache(df: pd.DataFrame) -> dict:
    return calcular_kpis_executivos(df)


@st.cache_data
def funil_operacional_cache(df: pd.DataFrame) -> pd.DataFrame:
    return funil_operacional(df)


@st.cache_data
def produtividade_por_nucleo_cache(df: pd.DataFrame) -> pd.DataFrame:
    return produtividade_por_nucleo(df)


@st.cache_data
def tabela_leadtime_por_cache(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    return tabela_leadtime_por(df, coluna)


@st.cache_data
def missing_por_coluna_cache(df: pd.DataFrame) -> pd.DataFrame:
    return missing_por_coluna(df)


@st.cache_data
def top_processos_criticos_cache(df: pd.DataFrame) -> pd.DataFrame:
    return top_processos_criticos(df)


# =================== HELPERS GERAIS ===================


def _inject_global_styles() -> None:
    """Aplica alguns estilos globais para deixar o layout mais moderno."""
    st.markdown(
        """
        <style>
        /* Afinar tipografia nas tabelas */
        .stDataFrame, .stDataframe {
            font-size: 0.9rem;
        }
        /* Suavizar separadores horizontais */
        hr {
            margin: 0.75rem 0 1.25rem 0 !important;
        }
        /* Sidebar levemente menor */
        section[data-testid="stSidebar"] * {
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _mapear_colunas(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Mapeia nomes amigáveis para as possíveis variações de colunas da base.
    Retorna apenas o *nome* da coluna (ou None se não encontrada).
    """
    return {
        "data_solic": achar_coluna(df, ["Data da solicitação", "Data da Solicitação"]),
        "orgao": achar_coluna(df, ["Orgão", "Órgão"]),
        "ug": achar_coluna(df, ["Unidade gestora", "Unidade Gestora", "UG"]),
        "nucleo": achar_coluna(df, ["Núcleo Pertencente", "Núcleo", "Nucleo"]),
        "tipo": achar_coluna(df, ["Tipo da solicitação", "Tipo da Solicitação", "Tipo Solicitação"]),
        "sit_proc": achar_coluna(df, ["Situação  do Processo", "Situação do Processo"]),
        "sit_atual": achar_coluna(df, ["Situação Atual", "Situacao Atual"]),
        "num_solic": achar_coluna(df, ["Número da Solicitação", "Numero da Solicitação"]),
        "resp": achar_coluna(df, ["Responsável", "Responsável Técnico", "Responsavel Tecnico"]),
        "status_macro": "status_macro" if "status_macro" in df.columns else None,
        "sla_categoria": "sla_categoria" if "sla_categoria" in df.columns else None,
        "risco_categoria": "risco_categoria" if "risco_categoria" in df.columns else None,
        "faixa_lead_time": "faixa_lead_time" if "faixa_lead_time" in df.columns else None,
    }


def _limpar_categoria(serie: pd.Series, vazio_label: str = "Não informado") -> pd.Series:
    """Padroniza texto de colunas categóricas, tratando vazios/nulos."""
    return (
        serie.astype(str)
        .str.strip()
        .replace({"": vazio_label, "nan": vazio_label, "None": vazio_label})
    )


def _top_n_categoria(
    df: pd.DataFrame,
    col: str,
    n: int = 15,
    nome_total: str = "Total",
) -> pd.DataFrame:
    """Retorna tabela agrupada por categoria com contagem e Top N."""
    resumo = df.groupby(col).size().reset_index(name=nome_total)
    return resumo.sort_values(nome_total, ascending=False).head(n)


def _plot_barras_empilhadas(
    df: pd.DataFrame,
    col_categoria: Optional[str],
    col_status: Optional[str],
    categorias_top: List[str],
    titulo: str,
    xaxis_title: str,
) -> None:
    """
    Gráfico de barras empilhadas moderno para distribuição de status por categoria.
    """
    if col_categoria is None or col_status is None:
        return

    df_top = df[df[col_categoria].isin(categorias_top)].copy()
    if df_top.empty:
        st.info("Nenhum dado disponível para o gráfico empilhado com os filtros atuais.")
        return

    df_top[col_status] = _limpar_categoria(df_top[col_status])
    tabela_stack = (
        df_top.groupby([col_categoria, col_status])
        .size()
        .reset_index(name="quantidade")
    )

    fig = go.Figure()
    categorias_status = sorted(tabela_stack[col_status].unique())
    palette = px.colors.qualitative.Safe

    for i, status in enumerate(categorias_status):
        dados = tabela_stack[tabela_stack[col_status] == status]
        fig.add_bar(
            x=dados[col_categoria],
            y=dados["quantidade"],
            name=status,
            marker_color=palette[i % len(palette)],
            hovertemplate="<b>%{x}</b><br>Status: %{fullData.name}<br>Qtd: %{y:,}<extra></extra>",
        )

    fig.update_layout(
        barmode="stack",
        title=titulo,
        template="plotly_white",
        xaxis_title=xaxis_title,
        yaxis_title="Quantidade",
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=60, b=80),
        title_x=0.02,
        title_font=dict(size=18),
        legend_title_text="Status",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# =================== HELPERS DE SÉRIE TEMPORAL ===================


def _preparar_serie_mensal(df: pd.DataFrame, col_data: str) -> pd.DataFrame:
    """Prepara DataFrame agregado por mês com quantidade, mm3 e acumulado."""
    serie = pd.to_datetime(df[col_data], errors="coerce").dropna()
    if serie.empty:
        return pd.DataFrame(columns=["periodo", "quantidade", "data", "mm3", "acumulado"])

    counts = serie.dt.to_period("M").value_counts().sort_index()
    df_mes = counts.rename_axis("periodo").to_frame("quantidade").reset_index()

    df_mes["data"] = df_mes["periodo"].dt.to_timestamp()
    df_mes = df_mes.sort_values("data").reset_index(drop=True)

    df_mes["mm3"] = df_mes["quantidade"].rolling(3, min_periods=1).mean()
    df_mes["acumulado"] = df_mes["quantidade"].cumsum()

    return df_mes


# =================== FILTROS AVANÇADOS ===================


def _aplicar_filtros_avancados(df: pd.DataFrame, cols: Dict[str, Optional[str]]) -> pd.DataFrame:
    """
    Aplica filtros avançados na sidebar (período, órgão, UG, núcleo, tipo, SLA, risco, etc.)
    Retorna um novo DataFrame filtrado.
    """
    df_filtrado = df.copy()

    col_data_solic = cols["data_solic"]
    col_orgao = cols["orgao"]
    col_ug = cols["ug"]
    col_nucleo = cols["nucleo"]
    col_tipo = cols["tipo"]
    col_sit_proc = cols["sit_proc"]
    col_sit_atual = cols["sit_atual"]
    col_num_solic = cols["num_solic"]
    col_sla_cat = cols["sla_categoria"]
    col_risco_cat = cols["risco_categoria"]
    col_faixa_lead = cols["faixa_lead_time"]

    st.sidebar.markdown("### 🎯 Filtros avançados")

    # --------- Período ---------
    if col_data_solic is not None and col_data_solic in df_filtrado.columns:
        serie_datas = pd.to_datetime(df_filtrado[col_data_solic], errors="coerce")
        serie_validas = serie_datas.dropna()
        if not serie_validas.empty:
            data_min = serie_validas.min()
            data_max = serie_validas.max()
            date_default: Tuple = (data_min.date(), data_max.date())

            date_input = st.sidebar.date_input(
                "Período (Data da solicitação)",
                value=date_default,
            )

            # Pode vir como único date ou tupla
            if isinstance(date_input, tuple):
                if len(date_input) == 2:
                    data_ini, data_fim = date_input
                elif len(date_input) == 1:
                    data_ini = data_fim = date_input[0]
                else:
                    data_ini, data_fim = date_default
            else:
                data_ini = data_fim = date_input

            if data_ini and data_fim:
                # Garante ordem correta
                if data_ini > data_fim:
                    data_ini, data_fim = data_fim, data_ini

                mask_data = (serie_datas.dt.date >= data_ini) & (serie_datas.dt.date <= data_fim)
                df_filtrado = df_filtrado[mask_data]

    # --------- Helper multiselect categórico ---------
    def _multiselect_categ(label: str, coluna: Optional[str]) -> None:
        nonlocal df_filtrado
        if coluna is None or coluna not in df_filtrado.columns:
            return

        valores = (
            df_filtrado[coluna]
            .astype(str)
            .str.strip()
            .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            .dropna()
            .unique()
        )
        valores = sorted(valores)
        if not valores:
            return

        sel = st.sidebar.multiselect(label, valores)
        if sel:
            df_filtrado = df_filtrado[
                df_filtrado[coluna].astype(str).str.strip().isin(sel)
            ]

    _multiselect_categ("Órgão", col_orgao)
    _multiselect_categ("Unidade gestora", col_ug)
    _multiselect_categ("Núcleo Pertencente", col_nucleo)
    _multiselect_categ("Tipo da solicitação", col_tipo)
    _multiselect_categ("Situação do Processo", col_sit_proc)
    _multiselect_categ("Situação Atual", col_sit_atual)
    _multiselect_categ("Categoria de SLA", col_sla_cat)
    _multiselect_categ("Categoria de risco", col_risco_cat)
    _multiselect_categ("Faixa de Lead Time", col_faixa_lead)

    # --------- Filtro por apenas críticos (alto risco ou muito antigos) ---------
    mostrar_criticos = st.sidebar.checkbox("Mostrar apenas processos críticos", value=False)
    if mostrar_criticos:
        condicoes = []
        if "risco_categoria" in df_filtrado.columns:
            condicoes.append(df_filtrado["risco_categoria"].eq("Alto"))
        if "muito_antigo" in df_filtrado.columns:
            condicoes.append(df_filtrado["muito_antigo"] == True)

        if condicoes:
            cond_critico = condicoes[0]
            for c in condicoes[1:]:
                cond_critico |= c
            df_filtrado = df_filtrado[cond_critico]
        else:
            st.sidebar.info(
                "Para o filtro de processos críticos funcionar, é necessário ter "
                "as colunas 'risco_categoria' e/ou 'muito_antigo' na base."
            )

    # --------- Busca textual por número de solicitação (com session_state) ---------
    if "filtro_num_solic" not in st.session_state:
        st.session_state["filtro_num_solic"] = ""

    if col_num_solic is not None and col_num_solic in df_filtrado.columns:
        termo = st.sidebar.text_input(
            "Buscar por Número da Solicitação (contém, mínimo 3 caracteres)",
            value=st.session_state["filtro_num_solic"],
        )
        termo = termo.strip()
        st.session_state["filtro_num_solic"] = termo

        if len(termo) >= 3:
            df_filtrado = df_filtrado[
                df_filtrado[col_num_solic].astype(str).str.contains(termo, case=False, na=False)
            ]
        elif len(termo) > 0:
            st.sidebar.caption("Digite pelo menos 3 caracteres para aplicar a busca.")

    return df_filtrado


# =================== ANÁLISE TEMPORAL (VISÃO GERAL) ===================


def _analise_temporal(df: pd.DataFrame, col_data_solic: Optional[str]) -> None:
    """
    Evolução mensal com barras + média móvel de 3 meses + acumulado.
    Layout mais moderno com hover unificado.
    """
    if col_data_solic is None or col_data_solic not in df.columns:
        st.info(
            "Não foi possível gerar a análise temporal porque a coluna de data "
            "da solicitação não foi encontrada."
        )
        return

    df_mes = _preparar_serie_mensal(df, col_data_solic)
    if df_mes.empty:
        st.info("Não há datas válidas para a análise temporal com os filtros atuais.")
        return

    fig = go.Figure()

    # Barras de volume
    fig.add_bar(
        x=df_mes["data"],
        y=df_mes["quantidade"],
        name="Solicitações/mês",
        marker_color="#2563eb",
        opacity=0.9,
        hovertemplate="<b>%{x|%Y-%m}</b><br>Qtd: %{y:,}<extra></extra>",
    )

    # Linha média móvel
    fig.add_scatter(
        x=df_mes["data"],
        y=df_mes["mm3"],
        mode="lines+markers",
        name="Média móvel (3 meses)",
        line=dict(width=3, color="#10b981"),
        marker=dict(size=6),
        hovertemplate="<b>%{x|%Y-%m}</b><br>MM3: %{y:.1f}<extra></extra>",
    )

    # Linha acumulada (eixo secundário)
    fig.add_scatter(
        x=df_mes["data"],
        y=df_mes["acumulado"],
        mode="lines",
        name="Acumulado",
        line=dict(width=2, dash="dot", color="#6b7280"),
        yaxis="y2",
        hovertemplate="<b>%{x|%Y-%m}</b><br>Acumulado: %{y:,}<extra></extra>",
    )

    fig.update_layout(
        title="Evolução mensal de solicitações",
        template="plotly_white",
        xaxis_title="Mês",
        yaxis_title="Quantidade",
        yaxis2=dict(
            title="Acumulado",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        margin=dict(l=20, r=40, t=60, b=40),
        title_x=0.02,
        title_font=dict(size=18),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )

    fig.update_xaxes(showgrid=True, gridcolor="#e5e7eb")
    fig.update_yaxes(showgrid=True, gridcolor="#e5e7eb")

    st.plotly_chart(fig, use_container_width=True)


# =================== DASHBOARD PRINCIPAL ===================


def render_dashboard(df: pd.DataFrame) -> None:
    """
    Dashboard principal com filtros avançados, layout moderno, caching e gráficos robustos.
    """
    _inject_global_styles()

    # Garante colunas de risco antes de mapear
    if "risco_score" not in df.columns or "risco_categoria" not in df.columns:
        df = calcular_risco(df)

    cols = _mapear_colunas(df)

    # --------- Filtros ---------
    df_filtrado = _aplicar_filtros_avancados(df, cols)
    st.caption(f"Total de registros após filtros: **{len(df_filtrado)}**")

    # Área opcional de debug / info (útil em ambiente interno)
    with st.expander("🔧 Informações técnicas (colunas mapeadas)", expanded=False):
        st.json(cols)

    abas = st.tabs([t["label"] for t in TABS_CONFIG])
    (
        aba_geral,
        aba_orgao,
        aba_nucleo,
        aba_sla,
        aba_risco,
        aba_dados,
        aba_ia,
    ) = abas

    # =======================================================
    # ========== ABA 1 – VISÃO GERAL ========================
    # =======================================================
    with aba_geral:
        section_title("Painel Executivo – Visão Geral")

        kpis = kpis_executivos_cache(df_filtrado)
        calcular_kpis_avancados(df_filtrado)  # mantido para uso nas outras abas (efeitos colaterais internos)

        # KPIs em cards
        with st.container():
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                card_kpi("Total Solicitações", kpis.get("Total Solicitações", 0))
            with col2:
                card_kpi("Concluídas", kpis.get("Concluídas", 0), helper="Processos finalizados")
            with col3:
                card_kpi("Taxa Conclusão (%)", kpis.get("Taxa Conclusão (%)", 0))
            with col4:
                card_kpi("Taxa Atraso (%)", kpis.get("Taxa Atraso (%)", 0))

        st.markdown("---")
        section_subtitle("📍 Funil Operacional (Status Macro)")

        funil = funil_operacional_cache(df_filtrado)
        if not funil.empty:
            total_funil = funil["quantidade"].sum()
            funil["%"] = (funil["quantidade"] / total_funil * 100).round(1)
            funil = funil.sort_values("quantidade", ascending=False).reset_index(drop=True)

            col_tabela, col_graf1, col_graf2 = st.columns([1.2, 1.6, 1.6])

            with col_tabela:
                st.dataframe(funil, use_container_width=True, height=260)

            with col_graf1:
                mostrar_grafico_barras(
                    funil,
                    "status_macro",
                    "quantidade",
                    "Quantidade por status macro",
                )

            with col_graf2:
                mostrar_grafico_pizza(
                    funil,
                    "status_macro",
                    "quantidade",
                    "Participação por status macro",
                )
        else:
            st.info(
                "Não foi possível calcular o funil operacional. "
                "Verifique se a base possui uma coluna de status macro ou situação dos processos."
            )

        st.markdown("---")
        section_subtitle("📆 Evolução Mensal de Solicitações")
        _analise_temporal(df_filtrado, cols["data_solic"])

    # =======================================================
    # ========== ABA 2 – ÓRGÃO & UG =========================
    # =======================================================
    with aba_orgao:
        section_title("Análises por Órgão & Unidade Gestora", icon="🏛")

        col_orgao = cols["orgao"]
        col_ug = cols["ug"]
        col_sit_atual = cols["sit_atual"]

        if col_orgao is None and col_ug is None:
            st.warning(
                "Não há colunas de Órgão ou Unidade Gestora na base. "
                "Verifique se os nomes das colunas estão corretos na planilha."
            )
        else:
            # ---------- KPIs de nível Órgão / UG ----------
            section_subtitle("🔎 Visão consolidada por Órgão/UG")

            total_orgaos = df_filtrado[col_orgao].nunique() if col_orgao else 0
            total_ugs = df_filtrado[col_ug].nunique() if col_ug else 0

            orgao_top, orgao_top_qtd = "", 0
            if col_orgao:
                cont_orgao = df_filtrado[col_orgao].value_counts(dropna=True)
                if not cont_orgao.empty:
                    orgao_top = cont_orgao.index[0]
                    orgao_top_qtd = cont_orgao.iloc[0]

            ug_top, ug_top_qtd = "", 0
            if col_ug:
                cont_ug = df_filtrado[col_ug].value_counts(dropna=True)
                if not cont_ug.empty:
                    ug_top = cont_ug.index[0]
                    ug_top_qtd = cont_ug.iloc[0]

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                card_kpi("Total de Órgãos", total_orgaos)
            with c2:
                card_kpi("Total de UGs", total_ugs)
            with c3:
                card_kpi("Órgão com mais solicitações", orgao_top_qtd, helper=orgao_top or "-")
            with c4:
                card_kpi("UG com mais solicitações", ug_top_qtd, helper=ug_top or "-")

            st.markdown("---")

            # ---------- Tabela e gráficos por Órgão ----------
            if col_orgao:
                section_subtitle("📌 Distribuição por Órgão")

                resumo_orgao = (
                    df_filtrado.groupby(col_orgao)
                    .size()
                    .reset_index(name="Total")
                    .sort_values("Total", ascending=False)
                )

                if resumo_orgao.empty:
                    st.info("Nenhum dado de Órgão encontrado com os filtros atuais.")
                else:
                    st.markdown("**Top 20 Órgãos por volume de solicitações**")
                    st.dataframe(resumo_orgao.head(20), use_container_width=True)

                    top15 = resumo_orgao.head(15)
                    mostrar_grafico_barras(
                        top15,
                        col_orgao,
                        "Total",
                        "Top 15 Órgãos por quantidade de solicitações",
                    )

                    # Situação Atual empilhada (se existir)
                    if col_sit_atual:
                        st.markdown("---")
                        section_subtitle("📊 Situação Atual das solicitações por Órgão (Top 10)")

                        top10_nomes = resumo_orgao.head(10)[col_orgao].tolist()
                        _plot_barras_empilhadas(
                            df_filtrado,
                            col_orgao,
                            col_sit_atual,
                            top10_nomes,
                            "Distribuição de Situação Atual – Top 10 Órgãos",
                            "Órgão",
                        )

            st.markdown("---")

            # ---------- Tabela e gráficos por UG ----------
            if col_ug:
                section_subtitle("🏢 Distribuição por Unidade Gestora")

                resumo_ug = (
                    df_filtrado.groupby(col_ug)
                    .size()
                    .reset_index(name="Total")
                    .sort_values("Total", ascending=False)
                )

                if resumo_ug.empty:
                    st.info("Nenhum dado de Unidade Gestora encontrado com os filtros atuais.")
                else:
                    st.markdown("**Top 20 UGs por volume de solicitações**")
                    st.dataframe(resumo_ug.head(20), use_container_width=True)

                    top15_ug = resumo_ug.head(15)
                    mostrar_grafico_barras(
                        top15_ug,
                        col_ug,
                        "Total",
                        "Top 15 UGs por quantidade de solicitações",
                    )

                    if col_sit_atual:
                        st.markdown("---")
                        section_subtitle("📊 Situação Atual das solicitações por UG (Top 10)")

                        top10_ug_nomes = resumo_ug.head(10)[col_ug].tolist()
                        _plot_barras_empilhadas(
                            df_filtrado,
                            col_ug,
                            col_sit_atual,
                            top10_ug_nomes,
                            "Distribuição de Situação Atual – Top 10 UGs",
                            "UG",
                        )

            # ---------- Heatmap Órgão x UG ----------
            if col_orgao and col_ug:
                st.markdown("---")
                section_subtitle("🗺 Mapa Órgão x Unidade Gestora (volume)")
                mostrar_heatmap(df_filtrado, col_orgao, col_ug, "Relação Órgão x UG (contagem)")

    # =======================================================
    # ========== ABA 3 – NÚCLEO & RESPONSÁVEL ===============
    # =======================================================
    with aba_nucleo:
        section_title("Desempenho por Núcleo & Responsável", icon="👥")

        col_nucleo = cols["nucleo"]
        col_resp = cols["resp"]
        col_status_macro = cols["status_macro"]

        # ---------- KPIs específicos ----------
        section_subtitle("🔎 Visão consolidada por Núcleo/Responsável")

        total_nucleos = df_filtrado[col_nucleo].nunique() if col_nucleo else 0
        total_responsaveis = df_filtrado[col_resp].nunique() if col_resp else 0

        nucleo_top, nucleo_top_qtd = "", 0
        if col_nucleo:
            vc_nucleo = df_filtrado[col_nucleo].value_counts(dropna=True)
            if not vc_nucleo.empty:
                nucleo_top = vc_nucleo.index[0]
                nucleo_top_qtd = vc_nucleo.iloc[0]

        resp_top, resp_top_qtd = "", 0
        if col_resp:
            vc_resp = df_filtrado[col_resp].value_counts(dropna=True)
            if not vc_resp.empty:
                resp_top = vc_resp.index[0]
                resp_top_qtd = vc_resp.iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            card_kpi("Total de Núcleos", total_nucleos)
        with c2:
            card_kpi("Total de Responsáveis", total_responsaveis)
        with c3:
            card_kpi("Núcleo com mais solicitações", nucleo_top_qtd, helper=nucleo_top or "-")
        with c4:
            card_kpi("Responsável com mais solicitações", resp_top_qtd, helper=resp_top or "-")

        st.markdown("---")

        # ---------- Produtividade por Núcleo ----------
        section_subtitle("📌 Produtividade por Núcleo")

        tabela_nucleo = produtividade_por_nucleo_cache(df_filtrado)
        if not tabela_nucleo.empty:
            if "Total" in tabela_nucleo.columns:
                tabela_nucleo = tabela_nucleo.sort_values("Total", ascending=False)
            st.dataframe(tabela_nucleo, use_container_width=True)
        else:
            st.info(
                "Não foi possível calcular produtividade por núcleo. "
                "Verifique se a base possui coluna de Núcleo e dados de conclusão."
            )

        # Top 15 Núcleos por volume
        if col_nucleo:
            resumo_nucleo = (
                df_filtrado.groupby(col_nucleo)
                .size()
                .reset_index(name="Total")
                .sort_values("Total", ascending=False)
            )
            if resumo_nucleo.empty:
                st.info("Nenhum dado de Núcleo encontrado com os filtros atuais.")
            else:
                top15_nucleo = resumo_nucleo.head(15)

                st.markdown("---")
                section_subtitle("📊 Top 15 Núcleos por volume de solicitações")
                mostrar_grafico_barras(
                    top15_nucleo,
                    col_nucleo,
                    "Total",
                    "Top 15 Núcleos por quantidade de solicitações",
                )

        # Gráfico empilhado: status_macro por Núcleo (se existir)
        if col_nucleo and col_status_macro:
            st.markdown("---")
            section_subtitle("📊 Distribuição de Status Macro por Núcleo (Top 10)")

            resumo_nucleo = (
                df_filtrado.groupby(col_nucleo)
                .size()
                .reset_index(name="Total")
                .sort_values("Total", ascending=False)
            )
            top10_nomes = resumo_nucleo.head(10)[col_nucleo].tolist()

            _plot_barras_empilhadas(
                df_filtrado,
                col_nucleo,
                col_status_macro,
                top10_nomes,
                "Distribuição de Status Macro – Top 10 Núcleos",
                "Núcleo",
            )

        st.markdown("---")
        section_subtitle("🏅 Ranking de Responsáveis")

        if col_resp:
            tabela_resp = tabela_leadtime_por_cache(df_filtrado, col_resp)
            if not tabela_resp.empty:
                if "Total" in tabela_resp.columns:
                    tabela_resp = tabela_resp.sort_values("Total", ascending=False)
                elif "Média" in tabela_resp.columns:
                    tabela_resp = tabela_resp.sort_values("Média", ascending=False)

                st.markdown("**Top 50 Responsáveis**")
                st.dataframe(tabela_resp.head(50), use_container_width=True)

                # Gráfico: Top 15 responsáveis por quantidade
                if "Total" in tabela_resp.columns:
                    top15_resp = tabela_resp.head(15).reset_index()
                    nome_col_resp = tabela_resp.index.name or col_resp or "Responsável"
                    if nome_col_resp is None:
                        top15_resp = top15_resp.rename(columns={"index": "Responsável"})
                        nome_col_resp = "Responsável"

                    mostrar_grafico_barras(
                        top15_resp,
                        nome_col_resp,
                        "Total",
                        "Top 15 Responsáveis por quantidade de solicitações",
                    )
            else:
                st.info(
                    "Não foi possível montar o ranking de responsáveis. "
                    "Verifique se a base possui lead time e responsáveis preenchidos."
                )
        else:
            st.info("Coluna de Responsável não encontrada na base.")

    # =======================================================
    # ========== ABA 4 – SLA & LEAD TIME ====================
    # =======================================================
    with aba_sla:
        section_title("SLA & Lead Time", icon="⏱")

        # SLA
        if cols["sla_categoria"] and cols["sla_categoria"] in df_filtrado.columns:
            section_subtitle("Distribuição por Categoria de SLA")
            dist_sla = (
                df_filtrado[cols["sla_categoria"]]
                .value_counts()
                .rename_axis("sla_categoria")
                .to_frame("Total")
                .reset_index()
                .sort_values("Total", ascending=False)
            )
            if dist_sla.empty:
                st.info("Nenhum dado de SLA encontrado com os filtros atuais.")
            else:
                col_tab, col_graf = st.columns([1, 2])
                with col_tab:
                    st.dataframe(dist_sla, use_container_width=True)
                with col_graf:
                    mostrar_grafico_barras(
                        dist_sla,
                        "sla_categoria",
                        "Total",
                        "Distribuição por Categoria de SLA",
                    )
        else:
            st.info(
                "Coluna 'sla_categoria' não encontrada na base. "
                "Certifique-se de que o ETL gerou essa informação."
            )

        st.markdown("---")
        # Faixa de lead time
        if cols["faixa_lead_time"] and cols["faixa_lead_time"] in df_filtrado.columns:
            section_subtitle("Distribuição por Faixa de Lead Time")
            dist_faixa = (
                df_filtrado[cols["faixa_lead_time"]]
                .value_counts()
                .rename_axis("faixa_lead_time")
                .to_frame("Total")
                .reset_index()
                .sort_values("Total", ascending=False)
            )
            if dist_faixa.empty:
                st.info("Nenhum dado de faixa de lead time encontrado com os filtros atuais.")
            else:
                col_tab2, col_graf2 = st.columns([1, 2])
                with col_tab2:
                    st.dataframe(dist_faixa, use_container_width=True)
                with col_graf2:
                    mostrar_grafico_barras(
                        dist_faixa,
                        "faixa_lead_time",
                        "Total",
                        "Quantidade por faixa de lead time",
                    )

        st.markdown("---")
        if "lead_time" in df_filtrado.columns:
            section_subtitle("Resumo estatístico de Lead Time")
            if df_filtrado["lead_time"].dropna().empty:
                st.info("Não há valores de lead_time preenchidos com os filtros atuais.")
            else:
                st.dataframe(df_filtrado["lead_time"].describe().to_frame("lead_time"), use_container_width=True)
        else:
            st.info("Coluna 'lead_time' não encontrada na base.")

    # =======================================================
    # ========== ABA 5 – RISCO ==============================
    # =======================================================
    with aba_risco:
        section_title("Mapa de Risco", icon="⚠️")

        colunas_risco = [
            c
            for c in [
                "Número da Solicitação",
                "Responsável",
                "lead_time",
                "risco_score",
                "risco_categoria",
                "risco_dimensao_principal",
            ]
            if c in df_filtrado.columns
        ]
        if colunas_risco:
            df_risco = df_filtrado[colunas_risco].copy()
            if "risco_score" in df_risco.columns:
                df_risco = df_risco.sort_values("risco_score", ascending=False)
            st.dataframe(
                df_risco,
                use_container_width=True,
                height=400,
            )
        else:
            st.info(
                "Não há colunas suficientes para detalhar o risco. "
                "Certifique-se de que o cálculo de risco foi aplicado na base."
            )

        st.markdown("---")
        if "risco_categoria" in df_filtrado.columns:
            resumo_risco = (
                df_filtrado["risco_categoria"]
                .value_counts()
                .rename_axis("Categoria")
                .to_frame("Quantidade")
                .reset_index()
                .sort_values("Quantidade", ascending=False)
            )
            if resumo_risco.empty:
                st.info("Nenhum dado de categoria de risco encontrado com os filtros atuais.")
            else:
                section_subtitle("Resumo por categoria de risco")
                st.dataframe(resumo_risco, use_container_width=True)
                mostrar_grafico_barras(
                    resumo_risco,
                    "Categoria",
                    "Quantidade",
                    "Distribuição por categoria de risco",
                )

        if "risco_dimensao_principal" in df_filtrado.columns:
            st.markdown("---")
            section_subtitle("Dimensões de risco (Tempo / Operacional / Governança)")
            dist_dim = (
                df_filtrado["risco_dimensao_principal"]
                .value_counts()
                .rename_axis("Dimensão")
                .to_frame("Quantidade")
                .reset_index()
                .sort_values("Quantidade", ascending=False)
            )
            if dist_dim.empty:
                st.info("Nenhum dado de dimensão de risco encontrado com os filtros atuais.")
            else:
                st.dataframe(dist_dim, use_container_width=True)
                mostrar_grafico_barras(
                    dist_dim,
                    "Dimensão",
                    "Quantidade",
                    "Distribuição por dimensão de risco",
                )

    # =======================================================
    # ========== ABA 6 – DADOS FILTRADOS + QUALIDADE ========
    # =======================================================
    with aba_dados:
        section_title("Dados Filtrados", icon="📂")

        st.dataframe(df_filtrado, use_container_width=True, height=350)

        csv = df_filtrado.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Baixar dados filtrados (CSV)",
            data=csv,
            file_name="dados_filtrados_solicitacoes.csv",
            mime="text/csv",
        )

        st.markdown("---")
        section_subtitle("Qualidade dos dados (faltantes e em branco)")

        tabela_missing = missing_por_coluna_cache(df_filtrado)
        if not tabela_missing.empty:
            tabela_top = tabela_missing.sort_values("faltantes", ascending=False).head(15)
            st.dataframe(tabela_top, use_container_width=True)

            mostrar_grafico_barras(
                tabela_top,
                "coluna",
                "faltantes",
                "Colunas com maior quantidade de dados faltantes/vazios",
            )
        else:
            st.info(
                "Não foi possível calcular faltantes. "
                "O dataframe está vazio ou não há colunas numéricas/categóricas válidas."
            )

    # ========== ABA 7 – IA ==========
    with aba_ia:
        section_title("Relatório Inteligente", icon="🤖")
        st.write(
            "Esta aba gera análises automáticas a partir dos dados filtrados, "
            "incluindo relatório analítico, checklist por Núcleo e modelo de ata de reunião."
        )

        # ---- Tipo de saída ----
        tipo_saida = st.radio(
            "Tipo de saída",
            [
                "Relatório analítico completo",
                "Checklist de ação por Núcleo",
                "Modelo de ata de reunião",
            ],
            index=0,
            horizontal=False,
        )

        # ---- Modo e nível de detalhe ----
        modo = st.selectbox(
            "Modo de análise",
            [
                "Executivo (geral)",
                "Focado em Órgão & UG",
                "Focado em Núcleo & Responsável",
            ],
        )

        nivel_detalhe = st.radio(
            "Nível de detalhe",
            ["Resumido", "Padrão", "Detalhado"],
            index=1,
            horizontal=True,
        )

        # Filtro de período específico para o relatório de IA
        col_data_solic = achar_coluna(df_filtrado, ["Data da solicitação", "Data da Solicitação"])

        opcoes_periodo = [
            "Mesmos dados da dashboard (sem filtro extra)",
            "Últimos 30 dias",
            "Últimos 90 dias",
            "Ano atual",
        ]
        periodo_escolhido = st.selectbox(
            "Período focado apenas para a IA",
            opcoes_periodo,
        )

        df_relatorio = df_filtrado.copy()
        periodo_label = "Mesmos filtros da dashboard"

        if col_data_solic is not None:
            datas = pd.to_datetime(df_filtrado[col_data_solic], errors="coerce")
            datas_validas = datas.dropna()
            if not datas_validas.empty:
                hoje = datas_validas.max()
                if periodo_escolhido == "Últimos 30 dias":
                    limite = hoje - timedelta(days=30)
                    mask = (datas >= limite) & (datas <= hoje)
                    df_relatorio = df_filtrado[mask]
                    periodo_label = f"Últimos 30 dias até {hoje.date().isoformat()}"
                elif periodo_escolhido == "Últimos 90 dias":
                    limite = hoje - timedelta(days=90)
                    mask = (datas >= limite) & (datas <= hoje)
                    df_relatorio = df_filtrado[mask]
                    periodo_label = f"Últimos 90 dias até {hoje.date().isoformat()}"
                elif periodo_escolhido == "Ano atual":
                    ano = hoje.year
                    mask = datas.dt.year == ano
                    df_relatorio = df_filtrado[mask]
                    periodo_label = f"Ano de {ano}"
        else:
            if periodo_escolhido != "Mesmos dados da dashboard (sem filtro extra)":
                st.info(
                    "Não foi possível aplicar um período específico na aba IA porque a coluna de data da solicitação não foi encontrada. "
                    "O relatório será gerado com os mesmos filtros da dashboard."
                )

        st.caption(f"Registros considerados na IA: **{len(df_relatorio)}**")

        if df_relatorio.empty:
            st.warning(
                "Não há registros após combinar filtros da sidebar com o período selecionado para a IA."
            )
        else:
            # Recalcula indicadores
            kpis = calcular_kpis_executivos(df_relatorio)
            funil = funil_operacional(df_relatorio)
            top_criticos = top_processos_criticos(df_relatorio)

            if "risco_categoria" in df_relatorio.columns:
                risco_tab = df_relatorio["risco_categoria"].value_counts().to_dict()
            else:
                risco_tab = {}

            # Distribuição por Tipo da solicitação
            col_tipo_ctx = achar_coluna(
                df_relatorio,
                ["Tipo da solicitação", "Tipo da Solicitação", "Tipo Solicitação"],
            )
            if col_tipo_ctx is not None:
                vc_tipo = (
                    df_relatorio[col_tipo_ctx]
                    .astype(str)
                    .str.strip()
                    .replace({"": "Não informado", "nan": "Não informado", "None": "Não informado"})
                    .value_counts()
                )
                distrib_tipo_solic = vc_tipo.to_dict()
            else:
                distrib_tipo_solic = None

            # Distribuição por Situação Atual
            col_sit_atual_ctx = achar_coluna(
                df_relatorio,
                ["Situação Atual", "Situacao Atual"],
            )
            if col_sit_atual_ctx is not None:
                vc_sit = (
                    df_relatorio[col_sit_atual_ctx]
                    .astype(str)
                    .str.strip()
                    .replace({"": "Não informado", "nan": "Não informado", "None": "Não informado"})
                    .value_counts()
                )
                distrib_situacao_atual = vc_sit.to_dict()
            else:
                distrib_situacao_atual = None

            # Contexto Órgão & UG
            contexto_orgao = None
            col_orgao_ctx = achar_coluna(df_relatorio, ["Orgão", "Órgão"])
            col_ug_ctx = achar_coluna(df_relatorio, ["Unidade gestora", "Unidade Gestora", "UG"])

            if col_orgao_ctx is not None or col_ug_ctx is not None:
                contexto_orgao = {}
                if col_orgao_ctx is not None:
                    vc_orgao = df_relatorio[col_orgao_ctx].value_counts(dropna=True)
                    top_orgaos = [(idx, int(q)) for idx, q in vc_orgao.items()]
                    contexto_orgao["total_orgaos"] = df_relatorio[col_orgao_ctx].nunique()
                    contexto_orgao["top_orgaos"] = top_orgaos
                else:
                    contexto_orgao["total_orgaos"] = 0
                    contexto_orgao["top_orgaos"] = []

                if col_ug_ctx is not None:
                    vc_ug = df_relatorio[col_ug_ctx].value_counts(dropna=True)
                    top_ugs = [(idx, int(q)) for idx, q in vc_ug.items()]
                    contexto_orgao["total_ugs"] = df_relatorio[col_ug_ctx].nunique()
                    contexto_orgao["top_ugs"] = top_ugs
                else:
                    contexto_orgao["total_ugs"] = 0
                    contexto_orgao["top_ugs"] = []

            # Contexto Núcleo & Responsável
            contexto_nucleo = None
            col_nucleo_ctx = achar_coluna(df_relatorio, ["Núcleo Pertencente", "Núcleo", "Nucleo"])
            col_resp_ctx = achar_coluna(
                df_relatorio,
                ["Responsável", "Responsável Técnico", "Responsavel Tecnico"],
            )

            if col_nucleo_ctx is not None or col_resp_ctx is not None:
                contexto_nucleo = {}
                if col_nucleo_ctx is not None:
                    vc_nucleo = df_relatorio[col_nucleo_ctx].value_counts(dropna=True)
                    top_nucleos = [(idx, int(q)) for idx, q in vc_nucleo.items()]
                    contexto_nucleo["total_nucleos"] = df_relatorio[col_nucleo_ctx].nunique()
                    contexto_nucleo["top_nucleos"] = top_nucleos
                else:
                    contexto_nucleo["total_nucleos"] = 0
                    contexto_nucleo["top_nucleos"] = []

                if col_resp_ctx is not None:
                    vc_resp = df_relatorio[col_resp_ctx].value_counts(dropna=True)
                    top_resps = [(idx, int(q)) for idx, q in vc_resp.items()]
                    contexto_nucleo["total_responsaveis"] = df_relatorio[col_resp_ctx].nunique()
                    contexto_nucleo["top_responsaveis"] = top_resps
                else:
                    contexto_nucleo["total_responsaveis"] = 0
                    contexto_nucleo["top_responsaveis"] = []

        st.markdown("---")
        st.write("Clique no botão abaixo para gerar o conteúdo de IA escolhido.")

        if st.button("Gerar com IA"):
            if df_relatorio.empty:
                st.warning("Sem dados para gerar saída de IA.")
            else:
                funil_list = funil.to_dict(orient="records") if not funil.empty else []
                top_list = top_criticos.to_dict(orient="records") if not top_criticos.empty else []

                if tipo_saida == "Relatório analítico completo":
                    relatorio = gerar_relatorio_ia(
                        kpis,
                        risco_tab,
                        funil_list,
                        top_list,
                        modo=modo,
                        contexto_orgao=contexto_orgao,
                        contexto_nucleo=contexto_nucleo,
                        nivel_detalhe=nivel_detalhe,
                        periodo_label=periodo_label,
                        distrib_tipo_solic=distrib_tipo_solic,
                        distrib_situacao_atual=distrib_situacao_atual,
                    )
                elif tipo_saida == "Checklist de ação por Núcleo":
                    relatorio = gerar_checklist_ia(
                        kpis,
                        risco_tab,
                        contexto_nucleo,
                        periodo_label=periodo_label,
                        nivel_detalhe=nivel_detalhe,
                    )
                else:  # Modelo de ata de reunião
                    relatorio = gerar_ata_reuniao_ia(
                        kpis,
                        risco_tab,
                        funil_list,
                        contexto_orgao=contexto_orgao,
                        contexto_nucleo=contexto_nucleo,
                        periodo_label=periodo_label,
                        nivel_detalhe=nivel_detalhe,
                    )

                st.markdown(relatorio)
