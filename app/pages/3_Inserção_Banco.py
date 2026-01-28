import streamlit as st
import pandas as pd
from pathlib import Path
import sys
import time
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.insert_data import inserir_transacoes, registrar_log_ingestao
from app.utils.ui_components import exibir_preview, exibir_relatorio, preparar_retorno_ia, ir_para_dashboard, renderizar_cabecalho, configurar_estilo_visual, simplificar_msg_erro
from services.auth_manager import AuthManager

st.set_page_config(
    page_title="Inserção no Banco",
    layout="wide"
)

configurar_estilo_visual()

auth = AuthManager()
auth.verificar_autenticacao()

with st.sidebar:
    st.header("Navegação")
    
    if st.button("Voltar para Início", width='stretch'):
        st.switch_page("main.py")
        
    st.divider()
    st.caption("Confirmação final e persistência dos dados validados.")

renderizar_cabecalho(3, "Confirmação e gravação das transações no banco de dados.")


if "fila_arquivos" not in st.session_state or not st.session_state["fila_arquivos"]:
    st.info("Não há arquivos na fila de processamento.")
    if st.button("Voltar para Upload", type="primary"):
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
    st.success("Todos os arquivos válidos foram processados.")
    
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

with st.container(border=True):
    col_meta1, col_meta2 = st.columns([1, 2])
    col_meta1.metric("Arquivo Atual", f"{idx_atual + 1} de {total_files}")
    col_meta2.metric("Nome do Arquivo", arquivo_atual.nome)
    st.progress(idx_atual / total_files)

st.markdown("###")

if arquivo_atual.status == "CONCLUIDO":
    st.success(f"Processamento finalizado para: {arquivo_atual.nome}")
    
    exibir_relatorio(arquivo_atual.resultado_insercao, arquivo_atual.resultado_insercao["duracao"])
    
    ins = arquivo_atual.resultado_insercao.get("registros_inseridos", 0)
    dup = arquivo_atual.resultado_insercao.get("registros_duplicados", 0)
    
    if ins == 0 and dup == 0:
        st.error("Nenhum registro foi inserido. Isso indica uma falha na operação.")
        if st.button("Solicitar Correção à IA", type="primary", width='stretch'):
            preparar_retorno_ia(arquivo_atual, "Nenhum registro inserido (Rejeição Total pelo Banco)")
    
    else:
        if st.button("Próximo Arquivo", type="primary", width='stretch'):
            arquivo_atual.relatorio_visualizado = True
            st.rerun()

else:
    df_final = arquivo_atual.df_corrigido if arquivo_atual.df_corrigido is not None else arquivo_atual.df_original
    
    with st.expander("Visualizar Preview dos Dados a Inserir", expanded=True):
        exibir_preview(df_final)
    
    st.markdown("###")

    if st.session_state.get("erro_insercao_critico"):
        with st.container(border=True):
            msg_simplificada = simplificar_msg_erro(st.session_state.get("erro_insercao_msg", "Erro desconhecido"))
            st.error(f"Falha Crítica na Inserção: {msg_simplificada}")
            
            c_retry1, c_retry2 = st.columns(2)
            with c_retry1:
                if st.button("Tentar Novamente", width='stretch'):
                    del st.session_state["erro_insercao_critico"]
                    st.rerun()
            with c_retry2:
                if st.button("Solicitar Correção à IA", type="primary", width='stretch'):
                    preparar_retorno_ia(arquivo_atual, st.session_state.get("erro_insercao_msg"))
    
    else:
        st.warning("Atenção: A ação abaixo irá gravar os dados no banco de dados.")
        
        col_act1, col_act2 = st.columns([3, 1])
        
        with col_act1:
            if st.button("Confirmar Inserção", type="primary", width='stretch'):
                with st.status("Gravando dados no banco...", expanded=False) as status:
                    try:
                        inicio = time.time()
                        
                        df_final = df_final.replace({pd.NA: None, np.nan: None})
                        
                        resultado = inserir_transacoes(df_final)
                        fim = time.time()
                        duracao = fim - inicio

                        resultado["nome_arquivo"] = arquivo_atual.nome
                        
                        origem_script = "Não utilizado"
                        if arquivo_atual.fonte_correcao == "IA":
                             origem_script = "IA"
                        elif arquivo_atual.fonte_correcao == "CACHE":
                             origem_script = "Cache"
                        
                        resultado["origem_script"] = origem_script

                        inicio_real = getattr(arquivo_atual, "timestamp_upload", inicio)
                        duracao_total = fim - inicio_real
                        
                        total_sucesso = resultado.get("registros_inseridos", 0)
                        total_duplicados = resultado.get("registros_duplicados", 0)
                        total_erros = len(resultado.get("erros", []))

                        usou_ia = True if origem_script == "IA" else False
                        script_id = getattr(arquivo_atual, 'script_id', None)

                        registrar_log_ingestao(
                            arquivo_nome=arquivo_atual.nome,
                            registros_total=resultado.get("total_registros", 0),
                            registros_sucesso=total_sucesso,
                            registros_erro=total_erros,
                            usou_ia=usou_ia,
                            script_id=script_id,
                            duracao_segundos=duracao_total
                        )
                        
                        if total_sucesso == 0 and total_duplicados == 0 and total_erros > 0:
                            msg = str(resultado["erros"][0])
                            arquivo_atual.logger.registrar_erro("INSERCAO", "Falha Total", msg)
                            arquivo_atual.finalizar_insercao(resultado, duracao)
                            
                            st.session_state["erro_insercao_critico"] = True
                            st.session_state["erro_insercao_msg"] = msg
                            st.rerun()
                                
                        else:
                            arquivo_atual.finalizar_insercao(resultado, duracao)
                            status.update(label="Concluído", state="complete")
                            st.rerun()
                        
                    except Exception as e:
                        status.update(label="Erro crítico", state="error")
                        arquivo_atual.logger.registrar_erro("INSERCAO", "Exception", str(e))
                        
                        st.session_state["erro_insercao_critico"] = True
                        st.session_state["erro_insercao_msg"] = str(e)
                        st.rerun()

        with col_act2:
            if st.button("Pular Arquivo", type="secondary", width='stretch'):
                arquivo_atual.status = "CANCELADO"
                arquivo_atual.logger.registrar_cancelamento()
                st.rerun()