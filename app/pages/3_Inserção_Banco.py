import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.insert_data import inserir_transacoes
from app.utils.ui_components import exibir_preview, exibir_relatorio, preparar_retorno_ia, ir_para_dashboard

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
    1. Suba os arquivos CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)
    
    st.divider()
    if st.button("Ver Dashboard", width='stretch'):
        st.session_state["pagina_anterior"] = "pages/3_Inserção_Banco.py"
        st.switch_page("pages/4_Dashboard.py")

st.title("Inserção no Banco de Dados")
st.divider()

if "fila_arquivos" not in st.session_state or not st.session_state["fila_arquivos"]:
    st.warning("Fila de arquivos vazia.")
    if st.button("Voltar para Início", type="primary"):
        st.switch_page("main.py")
    st.stop()

arquivo_atual = None

idx_atual = 0

for i, f in enumerate(st.session_state["fila_arquivos"]):
    if f.status in ["PRONTO_VALIDO", "PRONTO_IA", "PRONTO_CACHE"]:
        arquivo_atual = f
        idx_atual = i
        break
    if f.status == "CONCLUIDO" and not f.relatorio_visualizado:
        arquivo_atual = f
        idx_atual = i
        break

if arquivo_atual is None:
    st.success("Todos os arquivos válidos foram processados!")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Voltar para Início", width='stretch'):
            st.session_state["fila_arquivos"] = []
            st.switch_page("main.py")
    with col2:
        if st.button("Ir para Dashboard", type="primary", width='stretch'):
            ir_para_dashboard()
    st.stop()

total_files = len(st.session_state["fila_arquivos"])
st.subheader(f"Arquivo {idx_atual + 1} de {total_files}: {arquivo_atual.nome}")
st.progress(idx_atual / total_files)

if arquivo_atual.status == "CONCLUIDO":
    st.success(f"Processamento finalizado para: {arquivo_atual.nome}")
    
    exibir_relatorio(arquivo_atual.resultado_insercao, arquivo_atual.resultado_insercao["duracao"])
    
    ins = arquivo_atual.resultado_insercao.get("registros_inseridos", 0)
    dup = arquivo_atual.resultado_insercao.get("registros_duplicados", 0)
    
    if ins == 0 and dup == 0:
        st.error("Atenção: Nenhum registro foi inserido. Isso indica falha crítica.")
        if st.button("Voltar para Correção IA", type="primary", width='stretch'):
            preparar_retorno_ia(arquivo_atual, "Nenhum registro inserido (Rejeição Total)")
    
    else:
        if st.button("Próximo Arquivo", type="primary", width='stretch'):
            arquivo_atual.relatorio_visualizado = True
            st.rerun()

else:
    df_final = arquivo_atual.df_corrigido if arquivo_atual.df_corrigido is not None else arquivo_atual.df_original
    
    exibir_preview(df_final)
    
    if st.session_state.get("erro_insercao_critico"):
        st.error(f"Falha Crítica na inserção: {st.session_state.get('erro_insercao_msg')}")
        
        c_retry1, c_retry2 = st.columns(2)
        with c_retry1:
            if st.button("Tentar Inserir Novamente", width='stretch'):
                del st.session_state["erro_insercao_critico"]
                st.rerun()
        with c_retry2:
            if st.button("Voltar para Correção IA", type="primary", width='stretch'):
                preparar_retorno_ia(arquivo_atual, st.session_state.get("erro_insercao_msg"))
    
    else:
        st.warning("Esta ação irá escrever os dados no banco de dados.")
        
        col_act1, col_act2 = st.columns([3, 1])
        
        with col_act1:
            if st.button("Confirmar Inserção", type="primary", width='stretch'):
                with st.status("Inserindo registros...", expanded=False) as status:
                    try:
                        inicio = time.time()
                        
                        df_final = df_final.replace({pd.NA: None, np.nan: None})
                        
                        resultado = inserir_transacoes(df_final)
                        duracao = time.time() - inicio
                        
                        total_sucesso = resultado.get("registros_inseridos", 0)
                        total_duplicados = resultado.get("registros_duplicados", 0)
                        total_erros = len(resultado.get("erros", []))
                        
                        if total_sucesso == 0 and total_duplicados == 0 and total_erros > 0:
                            msg = str(resultado["erros"][0])
                            arquivo_atual.logger.registrar_erro("INSERCAO", "Falha Total", msg)
                            arquivo_atual.finalizar_insercao(resultado, duracao)
                            arquivo_atual.logger.registrar_erro("INSERCAO", "Rejeição em Lote", "Nenhum registro aceito")
                            
                            st.session_state["erro_insercao_critico"] = True
                            st.session_state["erro_insercao_msg"] = msg
                            st.rerun()
                                
                        else:
                            arquivo_atual.finalizar_insercao(resultado, duracao)
                            status.update(label="Concluído!", state="complete")
                            st.rerun()
                        
                    except Exception as e:
                        status.update(label="Erro crítico!", state="error")
                        arquivo_atual.logger.registrar_erro("INSERCAO", "Exception", str(e))
                        
                        st.session_state["erro_insercao_critico"] = True
                        st.session_state["erro_insercao_msg"] = str(e)
                        st.rerun()

        with col_act2:
            if st.button("Pular", width='stretch'):
                arquivo_atual.status = "CANCELADO"
                arquivo_atual.logger.registrar_cancelamento()
                st.rerun()