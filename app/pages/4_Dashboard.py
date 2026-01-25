import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px

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

tokens_economizados = df['tokens_economizados'].sum()   

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    st.metric("Arquivos Processados", total_arquivos, delta=f"{taxa_sucesso:.1f}% Sucesso")
with kpi2:
    st.metric("Total Tokens Gastos", f"{total_tokens:,.0f}".replace(",", "."))
with kpi3:
    st.metric("Uso do Cache", f"{qtd_cache}", delta=f"{taxa_cache:.1f}% do Total")
with kpi4:
    st.metric("Tokens Economizados", f"{tokens_economizados:,.0f}".replace(",", "."))

st.divider()

col_graf1, col_graf2 = st.columns([1, 1])

with col_graf1:
    st.subheader("IA vs Cache")
    df_origem = df['origem_correcao'].value_counts().reset_index()
    df_origem.columns = ['Origem', 'Total']
    
    fig_pizza = px.pie(
        df_origem, 
        values='Total', 
        names='Origem', 
        hole=0.4,
        color='Origem',
        color_discrete_map={'IA': '#FF6B6B', 'CACHE': '#4ECDC4', 'NENHUMA': '#FFE66D'}
    )
    st.plotly_chart(fig_pizza, width='stretch')

with col_graf2:
    st.subheader("Consumo Diário")
    df['data'] = df['created_at'].dt.date
    df_diario = df.groupby('data')['tokens_gastos'].sum()
    
    st.bar_chart(df_diario, color="#4ECDC4")

col_graf3, col_graf4 = st.columns([1, 1])

with col_graf3:
    st.subheader("Tentativas da IA")
    st.caption("Frequência de tentativas necessárias por arquivo")
    
    df_ia = df[df['origem_correcao'] == 'IA']
    
    if not df_ia.empty:
        contagem = df_ia['tentativas_ia'].value_counts().reset_index()
        contagem.columns = ['Tentativas', 'Quantidade']
        
        fig = px.bar(
            contagem, 
            x='Tentativas', 
            y='Quantidade',
            text_auto=True,
            color_discrete_sequence=['#FF9F43']
        )
        
        fig.update_layout(
            xaxis=dict(
                tickmode='linear',
                tick0=1,
                dtick=1
            ),
            bargap=0.2
        )
        
        fig.update_traces(width=0.3)         
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("Sem dados de uso de IA para gerar histograma.")

with col_graf4:
    st.subheader("Registros de Erros")
    df_erros = df[df['status'] == 'FALHA']['tipo_erro'].value_counts()
    
    if not df_erros.empty:
        st.bar_chart(df_erros, horizontal=True, color="#FF6B6B")
    else:
        st.success("Nenhum erro registrado!")


st.divider()
st.subheader("Histórico Detalhado")

filtro_status = st.multiselect(
    "Filtrar Status:", 
    options=df['status'].unique(),
    default=df['status'].unique()
)

df_filtrado = df[df['status'].isin(filtro_status)]

st.dataframe(
    df_filtrado[[
        'created_at', 'arquivo_nome', 'status', 'origem_correcao', 
        'tokens_gastos', 'tentativas_ia', 'registros_inseridos'
    ]],
    width='stretch',
    hide_index=True,
    column_config={
        "created_at": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
        "tokens_gastos": st.column_config.NumberColumn("Tokens"),
        "tentativas_ia": st.column_config.NumberColumn("Tentativas"),
        "status": st.column_config.Column("Status")
    }
)