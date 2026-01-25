import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import altair as alt

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.logger import carregar_dados

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

    if st.button(texto_botao, width='stretch'):
        st.switch_page(origem_atual)

st.title("Monitoramento de Performance")
st.markdown("Visão geral da eficiência do processamento e custos.")
st.divider()

df = carregar_dados()

if df.empty:
    st.warning("Nenhum dado registrado ainda. Processe alguns arquivos para ver as métricas!")
    st.stop()

total_arquivos = len(df)
total_sucesso = len(df[df['status'] == 'CONCLUIDO'])
taxa_sucesso = (total_sucesso / total_arquivos * 100) if total_arquivos > 0 else 0

total_tokens = df['tokens_gastos'].sum()

qtd_cache = len(df[df['origem_correcao'] == 'CACHE'])
taxa_cache = (qtd_cache / total_arquivos * 100) if total_arquivos > 0 else 0

media_tokens_ia = df[df['origem_correcao'] == 'IA']['tokens_gastos'].mean()
if pd.isna(media_tokens_ia): media_tokens_ia = 0
tokens_economizados = qtd_cache * media_tokens_ia

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric("Arquivos Processados", total_arquivos, delta=f"{taxa_sucesso:.1f}% Sucesso")
with kpi2:
    st.metric("Total Tokens Gastos", f"{total_tokens:,.0f}".replace(",", "."))
with kpi3:
    st.metric("Uso do Cache", f"{qtd_cache}", delta=f"{taxa_cache:.1f}% do Total")
with kpi4:
    st.metric("Tokens Economizados (Est.)", f"{tokens_economizados:,.0f}".replace(",", "."))
