# app.py

import streamlit as st
from core.etl import carregar_base_tratada
from core.sla import aplicar_sla
from core.risco import calcular_risco
from ui.dashboards import render_dashboard

# --------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# --------------------------------------------------------------------
st.set_page_config(
    page_title="Monitoramento de Solicitações",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilização básica (pode ir refinando depois)
CUSTOM_CSS = """
<style>
    /* Título mais destacado */
    h1 {
        font-weight: 700 !important;
    }
    /* Opcional: deixar o fundo um pouco mais clean */
    .stApp {
        background-color: #f5f7fb;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --------------------------------------------------------------------
# FUNÇÃO DE CARGA E PRÉ-PROCESSAMENTO (COM CACHE)
# --------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def carregar_dados():
    """
    Carrega a base tratada, aplica SLA e calcula risco.
    Usando cache para não recalcular tudo a cada interação.
    """
    df = carregar_base_tratada()
    df = aplicar_sla(df)
    df = calcular_risco(df)
    return df


# --------------------------------------------------------------------
# APLICAÇÃO PRINCIPAL
# --------------------------------------------------------------------
def main():
    st.title("📊 Monitoramento Estratégico de Solicitações")

    with st.spinner("Carregando base, aplicando SLA e calculando risco..."):
        try:
            df = carregar_dados()
        except FileNotFoundError as e:
            st.error(
                "⚠️ Não foi possível encontrar o arquivo de dados.\n\n"
                "Verifique se o arquivo **`data/solicitacoes.xlsx`** existe na pasta do projeto "
                "e foi enviado para o GitHub (no caso do deploy em nuvem)."
            )
            st.exception(e)
            return
        except Exception as e:
            st.error("❌ Ocorreu um erro ao preparar a base de dados.")
            st.exception(e)
            return

    # Chama toda a lógica de visualização que você já tem em ui/dashboards.py
    render_dashboard(df)


if __name__ == "__main__":
    main()
