import streamlit as st
from pathlib import Path
import sys
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.logger import carregar_dados
from services.auth_manager import AuthManager
from app.utils.ui_components import configurar_estilo_visual, simplificar_msg_erro

CORES = {
    "IA": "#5C7CFA",            
    "CACHE": "#10B981",
    "Cache": "#10B981",         
    "NENHUMA": "#94A3B8",
    "Nenhuma": "#94A3B8",       
    "Sem Correção": "#94A3B8",  
    "Gastos (IA)": "#5C7CFA",   
    "Economizados (Cache)": "#10B981"
}

st.set_page_config(
    page_title="Dashboard",
    layout="wide"
)

configurar_estilo_visual()

auth = AuthManager()
auth.verificar_autenticacao()

st.header("Dashboard de Monitoramento")

with st.sidebar:
    st.header("Navegação")

    origem_atual = st.session_state.get("origem_dashboard", "main.py")
    
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
    
    if st.button("Configurações", width='stretch'):
        st.session_state["origem_config"] = "pages/4_Dashboard.py"
        st.switch_page("pages/9_Configuracoes.py")
        
    st.divider()
    st.caption("Visão analítica do processamento de arquivos.")

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

with st.container(border=True):
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric("Arquivos Processados", total_arquivos, delta=f"{taxa_sucesso:.1f}% Sucesso")
    with kpi2:
        st.metric("Total Tokens Gastos", f"{total_tokens:,.0f}".replace(",", "."))
    with kpi3:
        st.metric("Uso do Cache", f"{qtd_cache}", delta=f"{taxa_cache:.1f}% do Total")
    with kpi4:
        st.metric("Tokens Economizados", f"{tokens_economizados:,.0f}".replace(",", "."))

st.markdown("###")

col_graf1, col_graf2 = st.columns([1, 1])

with col_graf1:
    with st.container(border=True):
        st.subheader("Distribuição por Origem")
        df_origem = df['origem_correcao'].value_counts().reset_index()
        df_origem.columns = ['Origem', 'Total']
        
        df_origem['Origem'] = df_origem['Origem'].replace({'NENHUMA': 'Sem Correção', 'CACHE': 'Cache'})
        
        fig_pizza = px.pie(
            df_origem, 
            values='Total', 
            names='Origem', 
            hole=0.4,
            color='Origem',
            color_discrete_map=CORES,
            height=350 
        )
        st.plotly_chart(fig_pizza, width='stretch')

with col_graf2:
    with st.container(border=True):
        st.subheader("Consumo vs Economia Diária")
        
        df['data_obj'] = df['created_at'].dt.date
        
        df_diario = df.groupby('data_obj')[['tokens_gastos', 'tokens_economizados']].sum().reset_index()
        
        df_diario.columns = ['Data', 'Gastos (IA)', 'Economizados (Cache)']
        
        df_diario['Data_Formatada'] = df_diario['Data'].apply(lambda x: x.strftime('%d/%m/%Y'))
        
        fig_bar = px.bar(
            df_diario,
            x='Data_Formatada',
            y=['Gastos (IA)', 'Economizados (Cache)'], 
            barmode='group', 
            height=350,
            color_discrete_map=CORES
        )
        
        fig_bar.update_traces(
            width=0.35, 
        )
        
        fig_bar.update_layout(
            xaxis_title="Data",
            yaxis_title="Qtd. Tokens",
            legend_title="Tipo",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig_bar, width='stretch')

col_graf3, col_graf4 = st.columns([1, 1])

with col_graf3:
    with st.container(border=True):
        st.subheader("Eficiência da IA")
        st.caption("Tentativas necessárias para correção")
        
        df_ia = df[df['origem_correcao'] == 'IA']
        if not df_ia.empty:
            contagem = df_ia['tentativas_ia'].value_counts().reset_index()
            contagem.columns = ['Tentativas', 'Quantidade']
            
            fig = px.bar(
                contagem, 
                x='Tentativas', 
                y='Quantidade',
                text_auto=True,
                color_discrete_sequence=[CORES["IA"]],
                height=350
            )
            
            fig.update_layout(
                xaxis=dict(tickmode='linear', tick0=1, dtick=1),
                bargap=0.2
            )
            
            fig.update_traces(width=0.3)         
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Ainda não há dados suficientes de correções via IA.")

with col_graf4:
    with st.container(border=True):
        st.subheader("Log de Erros Recentes")
        st.caption("Últimos registros de falha no sistema")
        
        df_erros = df[df['status'] == 'FALHA'].copy()
        
        if not df_erros.empty:
            df_erros['mensagem_erro'] = df_erros['mensagem_erro'].apply(simplificar_msg_erro)
            st.dataframe(
                df_erros[['created_at', 'arquivo_nome', 'mensagem_erro']],
                width='stretch',
                height=350,
                hide_index=True,
                column_config={
                    "created_at": st.column_config.DatetimeColumn("Data", format="DD/MM HH:mm"),
                    "arquivo_nome": "Arquivo",
                    "mensagem_erro": st.column_config.TextColumn("Erro", width="large")
                }
            )
        else:
            st.success("Nenhum erro registrado nas últimas operações.")

st.divider()
st.subheader("Histórico Detalhado")

with st.expander("Filtros Avançados", expanded=False):
    filtro_status = st.multiselect(
        "Filtrar por Status:", 
        options=df['status'].unique(),
        default=df['status'].unique()
    )

df_filtrado = df[df['status'].isin(filtro_status)]

st.dataframe(
    df_filtrado[[
        'created_at', 'arquivo_nome', 'status', 'origem_correcao', 
        'tokens_gastos', 'tokens_economizados', 'tentativas_ia', 'registros_inseridos'
    ]],
    width='stretch',
    hide_index=True,
    column_config={
        "created_at": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY HH:mm"),
        "tokens_gastos": st.column_config.NumberColumn("Tokens"),
        "tentativas_ia": st.column_config.NumberColumn("Tentativas"),
        "registros_inseridos": st.column_config.NumberColumn("Inseridos"),
        "status": st.column_config.Column("Status")
    }
)