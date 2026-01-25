import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(
    page_title="Franq | Dashboard",
    page_icon=":bar_chart:",
    layout="wide"
)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.header("Dashboard de Monitoramento")

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

    st.divider()

    origem_atual = st.session_state.get("pagina_anterior", "main.py")
    
    if "main" in origem_atual:
        texto_botao = "Voltar para Início"
    elif "Correção" in origem_atual:
        texto_botao = "Voltar para Correção"
    elif "Inserção" in origem_atual:
        texto_botao = "Voltar para Inserção"
    else:
        texto_botao = "Voltar"

    if st.button(texto_botao, use_container_width=True):
        st.switch_page(origem_atual)
    