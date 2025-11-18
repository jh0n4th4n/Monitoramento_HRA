# app.py

import streamlit as st
from core.etl import carregar_base_tratada
from core.sla import aplicar_sla
from core.risco import calcular_risco
from ui.dashboards import render_dashboard

st.set_page_config(
    page_title="Monitoramento de Solicitações",
    page_icon="📈",
    layout="wide"
    initial_sidebar_state="expanded"
)

st.title("📊 Monitoramento Estratégico de Solicitações")

df = carregar_base_tratada()
df = aplicar_sla(df)
df = calcular_risco(df)

render_dashboard(df)
