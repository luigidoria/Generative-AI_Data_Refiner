import streamlit as st
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(
    page_title="Franq | Inserção no Banco",
    page_icon=":bar_chart:",
    layout="wide"
)

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Revise os dados corrigidos.
    2. Confirme a inserção no banco.
    3. Visualize o relatório de status.
    """)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Inserção no Banco de Dados")
st.divider()

if "df_corrigido" not in st.session_state or "validacao_aprovada" not in st.session_state:
    st.warning("Nenhum dado validado encontrado!")
    st.info("Por favor, volte para a página de Correção IA e valide os dados primeiro.")
    
    if st.button("Voltar para Correção IA", type="primary"):
        st.switch_page("app/pages/2_Correção_IA.py")
    st.stop()

df_corrigido = st.session_state["df_corrigido"]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total de Registros", len(df_corrigido))
with col2:
    st.metric("Colunas", len(df_corrigido.columns))
with col3:
    if "valor" in df_corrigido.columns:
        valor_total = df_corrigido["valor"].sum()
        st.metric("Valor Total", f"R$ {valor_total:,.2f}")

st.divider()

st.subheader("Preview dos Dados")
st.info("Revise os dados abaixo antes de confirmar a inserção no banco de dados.")

num_preview = min(10, len(df_corrigido))
st.dataframe(
    df_corrigido.head(num_preview),
    use_container_width=True,
    hide_index=False
)

if len(df_corrigido) > num_preview:
    st.caption(f"Mostrando {num_preview} de {len(df_corrigido)} registros.")

st.divider()

st.subheader("Confirmar Inserção")
st.warning("Esta ação irá inserir os dados no banco de dados. Certifique-se de que os dados estão corretos.")

col_confirmar, col_voltar = st.columns([1, 1])

with col_confirmar:
    if st.button("Confirmar e Inserir no Banco", type="primary", use_container_width=True):
        st.session_state["confirmar_insercao"] = True
        st.rerun()

with col_voltar:
    if st.button("Voltar para Correção", use_container_width=True):
        st.switch_page("app/pages/2_Correção_IA.py")

st.divider()

if st.button("Voltar para Início", use_container_width=True):
    st.switch_page("app/pages/main.py")
