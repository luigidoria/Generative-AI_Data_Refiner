import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation import validar_csv_completo
from app.utils.ui_components import formatar_titulo_erro, renderizar_cabecalho, configurar_estilo_visual
from app.services.script_cache import salvar_script_cache, buscar_script_cache, gerar_hash_estrutura
from app.services.ai_code_generator import gerar_codigo_correcao_ia
from app.utils.data_handler import carregar_template
from services.auth_manager import AuthManager

st.set_page_config(
    page_title="Correção IA",
    layout="wide"
)

configurar_estilo_visual()

auth = AuthManager()
auth.verificar_autenticacao()

with st.sidebar:
    st.header("Navegação")
    
    if st.button("Voltar para Lista", width='stretch'):
        st.switch_page("main.py")

    st.divider()
    st.caption("A IA analisará os erros e proporá um script de correção automática.")

renderizar_cabecalho(2, "Revisão e aplicação de correções assistidas por IA.")

if "fila_arquivos" not in st.session_state or not st.session_state["fila_arquivos"]:
    st.info("Não há arquivos pendentes na fila.")
    if st.button("Voltar para Upload", type="primary"):
        st.switch_page("main.py")
    st.stop()

arquivos_tarefa = [
    f for f in st.session_state["fila_arquivos"] 
    if f.status in ["PENDENTE_CORRECAO", "PRONTO_IA", "FALHA_MANUAL"]
]

arquivo_atual = next((f for f in arquivos_tarefa if f.status == "PENDENTE_CORRECAO"), None)

if arquivo_atual is None:
    if len(arquivos_tarefa) > 0:
        st.toast("Todas as correções foram concluídas! Avançando...", duration='short')
    else:
        st.toast("Nenhum arquivo precisa de correção. Avançando...", duration='short')
    
    st.switch_page("pages/3_Inserção_Banco.py")
    st.stop()

total_tarefas = len(arquivos_tarefa)
tarefas_concluidas = len([f for f in arquivos_tarefa if f.status != "PENDENTE_CORRECAO"])
indice_display = tarefas_concluidas + 1

with st.container(border=True):
    col_meta1, col_meta2, col_meta3 = st.columns(3)
    col_meta1.metric("Progresso da Correção", f"Arquivo {indice_display} de {total_tarefas}")
    col_meta2.metric("Arquivo", arquivo_atual.nome)
    col_meta3.metric("Erros Detectados", arquivo_atual.validacao["total_erros"])

    progresso = tarefas_concluidas / total_tarefas if total_tarefas > 0 else 0
    st.progress(progresso)

    with st.expander("Visualizar Detalhes dos Erros"):
        for i, erro in enumerate(arquivo_atual.validacao["detalhes"]):
            st.write(f"- {formatar_titulo_erro(erro.get('tipo'))}")

st.markdown("###")

session_key_code = f"code_gen_{arquivo_atual.id}"
session_key_meta = f"meta_gen_{arquivo_atual.id}"
session_key_exec = f"exec_ok_{arquivo_atual.id}"
session_key_error = f"gen_error_{arquivo_atual.id}"
session_key_auto = f"auto_run_{arquivo_atual.id}"
session_key_valid = f"valid_res_{arquivo_atual.id}"

ignorar_cache_flag = st.session_state.get(f"ignore_cache_{arquivo_atual.id}", False)

if session_key_code not in st.session_state:
    
    if session_key_auto not in st.session_state and not st.session_state.get(session_key_error) and not ignorar_cache_flag:
        colunas_hash = list(arquivo_atual.df_original.columns)
        hash_est = gerar_hash_estrutura(colunas_hash, arquivo_atual.validacao["detalhes"])
        script_cache = buscar_script_cache(hash_est)
        
        if script_cache:
            st.session_state[session_key_code] = script_cache["script"]
            st.session_state[session_key_meta] = {
                "hash": hash_est,
                "tokens": 0, 
                "econ": script_cache.get("custo_tokens", 0),
                "fonte": "CACHE",
                "vezes_utilizado": script_cache.get("vezes_utilizado", 0),
                "script_id": script_cache["id"]
            }
            arquivo_atual.update_ia_stats(0, "CACHE", script_cache.get("custo_tokens", 0))
            st.rerun()
    
    if session_key_error in st.session_state:
        st.error(f"Falha anterior: {st.session_state[session_key_error]}")

    if ignorar_cache_flag:
        st.caption("Gerando nova solução (Cache ignorado).")

    trigger_generation = False
    if session_key_auto in st.session_state:
        trigger_generation = True
    else:
        if st.button("Gerar Solução de Correção", type="primary"):
            trigger_generation = True

    if trigger_generation:
        if session_key_error in st.session_state:
            del st.session_state[session_key_error]
        
        if session_key_auto in st.session_state:
            del st.session_state[session_key_auto]
            
        if f"ignore_cache_{arquivo_atual.id}" in st.session_state:
            del st.session_state[f"ignore_cache_{arquivo_atual.id}"]

        with st.spinner("Analisando dados e gerando script..."):
            try:
                codigo, usou_cache, hash_est, s_id, qtd, tokens, econ = gerar_codigo_correcao_ia(
                    arquivo_atual.df_original, 
                    arquivo_atual.validacao,
                    ignorar_cache=ignorar_cache_flag
                )
                
                fonte_real = "CACHE" if usou_cache else "IA"
                
                st.session_state[session_key_code] = codigo
                st.session_state[session_key_meta] = {
                    "hash": hash_est,
                    "tokens": tokens,
                    "econ": econ,
                    "fonte": fonte_real,
                    "script_id": s_id,
                    "vezes_utilizado": qtd
                }
                
                arquivo_atual.update_ia_stats(tokens, fonte_real, econ)
                st.rerun()
                
            except Exception as e:
                arquivo_atual.logger.registrar_erro("GERACAO_SCRIPT", "API Error", str(e))
                st.session_state[session_key_error] = str(e)
                st.rerun()

else:
    meta = st.session_state[session_key_meta]
    codigo_atual = st.session_state[session_key_code]
    
    with st.container(border=True):
        st.markdown("#### Correção Automática Pronta")
        if meta["fonte"] == "CACHE":
            st.markdown(f":green[**O sistema reconheceu este tipo de erro e aplicou uma correção validada anteriormente.**] (Esta correção já foi aplicada {meta.get('vezes_utilizado', 0)} vezes)")
        else:
            st.markdown(":blue[**A Inteligência Artificial analisou os erros e gerou um novo script de correção.**]")
    
        with st.expander("Ver detalhes técnicos da correção (Script Python)", expanded=False):
            st.code(codigo_atual, language="python")
    
    if session_key_exec not in st.session_state:
        
        col_exec, col_desc = st.columns([1, 1])
        
        with col_exec:
            if st.button("Executar e Validar", type="primary", width='stretch'):
                try:
                    local_ns = {"df": arquivo_atual.df_original.copy(), "pd": pd, "np": np} 
                    exec(codigo_atual, local_ns)
                    df_temp = local_ns["df"]
                    
                    st.session_state[session_key_exec] = df_temp
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode='w', encoding='utf-8') as tmp:
                        df_temp.to_csv(tmp.name, index=False)
                        tmp_path = tmp.name
                    
                    try:
                        template = carregar_template()
                        res = validar_csv_completo(tmp_path, template)
                        st.session_state[session_key_valid] = res
                    finally:
                        os.remove(tmp_path)
                    
                    st.rerun()
                except Exception as e:
                    st.session_state[f"ignore_cache_{arquivo_atual.id}"] = True
                    st.error(f"Erro de Execução: {e}")
        
        with col_desc:
            if st.button("Descartar e Tentar Novamente", type="secondary", width='stretch'):
                del st.session_state[session_key_code]
                del st.session_state[session_key_meta]
                st.session_state[session_key_auto] = True
                if session_key_error in st.session_state: del st.session_state[session_key_error]
                st.rerun()
                
    else:
        df_temp = st.session_state[session_key_exec]
        res_valid = st.session_state.get(session_key_valid, {"valido": False})
        
        st.markdown("###")

        if res_valid["valido"]:
            with st.container(border=True):
                st.markdown("#### Resultado da Validação")
                st.success("Validação Aprovada")
                st.markdown("Os dados foram corrigidos e estão compatíveis com o modelo.")
                
                with st.expander("Visualizar Preview dos Dados"):
                    st.dataframe(df_temp, height=300, width='stretch')
                
                if st.button("Confirmar e Avançar", type="primary", width='stretch'):
                    arquivo_atual.df_corrigido = df_temp
                    arquivo_atual.status = "PRONTO_IA"
                    
                    if meta["fonte"] == "IA":
                        tipos_erros = [e.get("tipo") for e in arquivo_atual.validacao["detalhes"]]
                        script_id = salvar_script_cache(
                            meta["hash"], 
                            codigo_atual, 
                            f"Auto-fix: {tipos_erros}", 
                            tokens=meta["tokens"]
                        )
                        arquivo_atual.script_id = script_id
                    
                    if meta["fonte"] == "CACHE":
                        arquivo_atual.script_id = meta.get("script_id")

                    del st.session_state[session_key_code]
                    del st.session_state[session_key_meta]
                    del st.session_state[session_key_exec]
                    if session_key_valid in st.session_state: del st.session_state[session_key_valid]
                    if session_key_error in st.session_state: del st.session_state[session_key_error]
                    st.rerun()
        else:
            with st.container(border=True):
                st.markdown("#### Resultado da Validação")
                st.error(f"Ainda existem {res_valid.get('total_erros', '?')} erro(s) após a execução.")
                
                with st.expander("Ver Erros Restantes"):
                    for e in res_valid.get("detalhes", []):
                        st.write(f"- {formatar_titulo_erro(e.get('tipo'))}")

                with st.expander("Visualizar Dados Gerados"):
                    st.dataframe(df_temp, height=300, width='stretch')
                
                if st.button("Descartar e Gerar Novo Código", type="secondary", width='stretch'):
                    del st.session_state[session_key_code]
                    del st.session_state[session_key_meta]
                    del st.session_state[session_key_exec] 
                    if session_key_valid in st.session_state: del st.session_state[session_key_valid]
                    st.session_state[session_key_auto] = True
                    if session_key_error in st.session_state: del st.session_state[session_key_error]
                    st.session_state[f"ignore_cache_{arquivo_atual.id}"] = True
                    
                    st.rerun()

st.divider()

col_vazio, col_skip = st.columns([4, 1])

with col_skip:
    if st.button("Pular Arquivo", type="secondary", width='stretch'):
        arquivo_atual.status = "FALHA_MANUAL"
        arquivo_atual.logger.registrar_erro("GERACAO_SCRIPT", "Manual", "Usuario pulou o arquivo")
        
        if session_key_code in st.session_state: del st.session_state[session_key_code]
        if session_key_meta in st.session_state: del st.session_state[session_key_meta]
        if session_key_exec in st.session_state: del st.session_state[session_key_exec]
        if session_key_valid in st.session_state: del st.session_state[session_key_valid]
        if session_key_error in st.session_state: del st.session_state[session_key_error]
        if session_key_auto in st.session_state: del st.session_state[session_key_auto]
        
        st.rerun()