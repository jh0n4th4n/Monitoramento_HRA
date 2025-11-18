# ui/ui_components.py

import streamlit as st
import plotly.express as px
import pandas as pd


# ========== TÍTULOS / SUBTÍTULOS ==========

def section_title(text, icon="📊"):
    st.markdown(f"### {icon} {text}")


def section_subtitle(text):
    st.markdown(f"#### {text}")


# ========== CARDS KPI (SEM HTML) ==========

def _format_value(value):
    if isinstance(value, float):
        # formata float no padrão brasileiro
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def card_kpi(title, value, helper=None):
    """
    Card KPI usando apenas componentes nativos do Streamlit.
    - NÃO usa HTML → impossível aparecer tag <div>.
    - Aparência “profissional” vem do uso de colunas + st.metric.
    """
    val = _format_value(value)
    st.metric(label=title, value=val)
    if helper:
        st.caption(helper)


# ========== ALERTAS ==========

def exibir_alerta(texto, tipo="info"):
    if tipo == "success":
        st.success(texto)
    elif tipo == "warning":
        st.warning(texto)
    elif tipo == "error":
        st.error(texto)
    else:
        st.info(texto)


# ========== GRÁFICOS ==========

def mostrar_grafico_barras(df, x, y, title):
    """
    Gráfico de barras com ordenação por valor e rótulos rotacionados.
    """
    if df.empty or x not in df.columns or y not in df.columns:
        st.info("Sem dados suficientes para este gráfico.")
        return

    dados = df[[x, y]].copy()

    # Limpar categorias e valores nulos
    if pd.api.types.is_object_dtype(dados[x]) or pd.api.types.is_categorical_dtype(dados[x]):
        dados[x] = dados[x].astype(str).str.strip()
        dados[x] = dados[x].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    dados = dados.dropna(subset=[x, y])
    if dados.empty:
        st.info("Sem dados válidos após remover valores em branco.")
        return

    dados = dados.sort_values(y, ascending=False)

    fig = px.bar(
        dados,
        x=x,
        y=y,
        text=y,
        title=title,
    )
    fig.update_traces(textposition="outside")

    fig.update_layout(
        template="plotly_white",
        xaxis_title="",
        yaxis_title="",
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=60, b=80),
        title_x=0.02,
        title_font=dict(size=18),
    )

    st.plotly_chart(fig, use_container_width=True)


def mostrar_grafico_linha(df, x, y, title):
    """
    Gráfico de linha simples, com ordenação pelo eixo X.
    """
    if df.empty or x not in df.columns or y not in df.columns:
        st.info("Sem dados suficientes para este gráfico.")
        return

    dados = df[[x, y]].copy().dropna(subset=[x, y])
    if dados.empty:
        st.info("Sem dados válidos para este gráfico de linha.")
        return

    try:
        dados[x] = pd.to_datetime(dados[x])
        dados = dados.sort_values(x)
    except Exception:
        dados[x] = dados[x].astype(str)
        dados = dados.sort_values(x)

    fig = px.line(
        dados,
        x=x,
        y=y,
        markers=True,
        title=title,
    )

    fig.update_layout(
        template="plotly_white",
        xaxis_title="",
        yaxis_title="",
        margin=dict(l=20, r=20, t=60, b=40),
        title_x=0.02,
        title_font=dict(size=18),
    )

    st.plotly_chart(fig, use_container_width=True)


def mostrar_heatmap(df, x, y, title):
    """
    Mapa de calor para relação entre duas categorias (ex.: Órgão x UG).
    """
    if df.empty or x not in df.columns or y not in df.columns:
        st.info("Sem dados suficientes para este mapa.")
        return

    dados = df[[x, y]].copy()

    for col in [x, y]:
        if pd.api.types.is_object_dtype(dados[col]) or pd.api.types.is_categorical_dtype(dados[col]):
            dados[col] = dados[col].astype(str).str.strip()
            dados[col] = dados[col].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    dados = dados.dropna(subset=[x, y])
    if dados.empty:
        st.info("Sem dados para construir o mapa após remover vazios.")
        return

    tabela = dados.groupby([x, y]).size().reset_index(name="quantidade")

    fig = px.density_heatmap(
        tabela,
        x=x,
        y=y,
        z="quantidade",
        color_continuous_scale="Blues",
        title=title,
    )
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=80),
        xaxis_tickangle=-30,
        title_x=0.02,
        title_font=dict(size=18),
    )

    st.plotly_chart(fig, use_container_width=True)


def mostrar_grafico_pizza(df, names, values, title):
    """
    Gráfico de pizza / donut para proporção (ex.: status_macro).
    """
    if df.empty or names not in df.columns or values not in df.columns:
        st.info("Sem dados suficientes para este gráfico.")
        return

    dados = df[[names, values]].copy().dropna(subset=[names, values])
    if dados.empty:
        st.info("Sem dados válidos após remover valores em branco.")
        return

    fig = px.pie(
        dados,
        names=names,
        values=values,
        title=title,
        hole=0.4,  # donut
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=60, b=40),
        title_x=0.02,
        title_font=dict(size=18),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)
