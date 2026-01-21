import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Franq | Ingestão de Dados",
    page_icon=":bar_chart:",
    layout="wide"
)

st.title("Portal de Ingestão de Transações")
st.divider()

with st.sidebar:
    st.header("Configurações")
    st.caption("Sistema de Ingestão v1.0")
    st.divider()
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

container = st.container(border=True)
with container:
    st.markdown("### Upload de Arquivos")
    st.info("Faça o upload dos seus arquivos financeiros (CSV) para validação e correção automática via IA.")
    uploaded_file = st.file_uploader("Selecione o arquivo", type=["csv"], label_visibility="collapsed")
    if uploaded_file is not None:
        dataframe = pd.read_csv(uploaded_file)
        st.write(dataframe[:5])