import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import time

# Adiciona o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.insert_data import inserir_transacoes, registrar_log_ingestao
from app.utils.session_manager import limpar_sessao_para_inicio
from app.utils.ui_components import exibir_preview, exibir_relatorio
from app.services.logger import registrar_erro, registrar_conclusao

st.set_page_config(
    page_title="Franq | Inserção no Banco",
    page_icon=":bar_chart:",
    layout="wide"
)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { display: none; }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Revise os dados corrigidos.
    2. Confirme a inserção no banco.
    3. Visualize o relatório de status.
    """)

    st.divider()
    if st.button("Ver Dashboard", width='stretch'):
        st.session_state["pagina_anterior"] = "pages/3_Inserção_Banco.py"
        st.switch_page("pages/4_Dashboard.py")
    


st.title("Inserção no Banco de Dados")
st.divider()

if "df_corrigido" not in st.session_state or "validacao_aprovada" not in st.session_state:
    st.warning("Nenhum dado validado encontrado!")
    if st.button("Voltar para Correção IA", type="primary"):
        st.switch_page("pages/2_Correção_IA.py")
    st.stop()

df_corrigido = st.session_state["df_corrigido"]

if not st.session_state.get("insercao_concluida", False):
    
    exibir_preview(df_corrigido)

    st.warning("Esta ação irá escrever os dados no banco de dados.")

    if st.button("Confirmar Inserção", type="primary", width='stretch'):
        
        with st.status("Processando ingestão de dados...", expanded=False) as status:
            try:
                inicio = time.time()
                
                st.write("Conectando ao banco de dados...")

                st.write("Inserindo registros...")
                resultado = inserir_transacoes(df_corrigido)
                
                duracao = time.time() - inicio
                
                st.write("Registrando logs de auditoria...")
                arquivo_nome = st.session_state.get("nome_arquivo", "unknown.csv")
                script_id = st.session_state.get("script_id_cache")
                
                total_sucesso = resultado.get("registros_inseridos", 0)
                total_erros_geral = len(resultado.get("erros", []))
                erros_duplicados = resultado.get("registros_duplicados", 0)
                erros_reais = total_erros_geral - erros_duplicados
                
                registrar_log_ingestao(
                    arquivo_nome=arquivo_nome,
                    registros_total=resultado.get("total_registros", 0),
                    registros_sucesso=total_sucesso,
                    registros_erro=erros_reais,
                    usou_ia=(script_id is not None),
                    script_id=script_id,
                    duracao_segundos=duracao
                )

                registrar_conclusao(total_sucesso, erros_duplicados, erros_reais)
                
                status.update(label="Processo concluído!", state="complete", expanded=False)
                
                st.session_state["resultado_insercao"] = resultado
                st.session_state["duracao_insercao"] = duracao
                st.session_state["insercao_concluida"] = True
                st.rerun()

            except Exception as e:
                registrar_erro("INSERCAO_DADOS", "Erro Inserção", str(e))
                status.update(label="Erro crítico!", state="error")
                st.error(f"Falha na inserção: {str(e)}")
                st.stop()

    if st.session_state.get("sem_modficadoes_necessarias", False):
        if st.button("Voltar para Upload", width='stretch'):
            st.switch_page("main.py")
    
    else:
        if st.button("Voltar para Correção", width='stretch'):
            st.switch_page("pages/2_Correção_IA.py")

else:
    resultado = st.session_state.get("resultado_insercao", {})
    duracao = st.session_state.get("duracao_insercao", 0)
    
    exibir_relatorio(resultado, duracao)
    
    if st.button("Finalizar e Voltar ao Início", type="primary", width='stretch'):
        limpar_sessao_para_inicio()
        st.switch_page("main.py")