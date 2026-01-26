import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.validation import validar_csv_completo
from app.utils.ui_components import formatar_titulo_erro
from app.services.script_cache import salvar_script_cache, buscar_script_cache, gerar_hash_estrutura
from app.services.ai_code_generator import gerar_codigo_correcao_ia
from app.utils.data_handler import carregar_template

st.set_page_config(
    page_title="Franq | Correção IA",
    page_icon=":bar_chart:",
    layout="wide"
)

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
        st.session_state["pagina_anterior"] = "pages/2_Correção_IA.py"
        st.switch_page("pages/4_Dashboard.py")

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Correção Automática via IA")
st.divider()

if "fila_arquivos" not in st.session_state or not st.session_state["fila_arquivos"]:
    st.warning("Fila vazia.")
    if st.button("Voltar para Upload"):
        st.switch_page("main.py")
    st.stop()

arquivo_atual = None
idx_atual = -1

for i, f in enumerate(st.session_state["fila_arquivos"]):
    if f.status == "PENDENTE_CORRECAO":
        arquivo_atual = f
        idx_atual = i
        break

if arquivo_atual is None:
    st.success("Todos os arquivos da fila foram processados!")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Voltar para Lista", width='stretch'):
            st.switch_page("main.py")
    with col2:
        if st.button("Ir para Inserção no Banco", type="primary", width='stretch'):
            st.switch_page("pages/3_Inserção_Banco.py")
    st.stop()

total_files = len(st.session_state["fila_arquivos"])
st.subheader(f"Processando arquivo {idx_atual + 1} de {total_files}: {arquivo_atual.nome}")
st.progress((idx_atual) / total_files)

col_info1, col_info2, col_info3 = st.columns(3)
col_info1.metric("Erros", arquivo_atual.validacao["total_erros"])
col_info2.metric("Linhas", len(arquivo_atual.df_original))
col_info3.metric("Status", "Aguardando Correção")

with st.expander("Detalhes dos Erros", expanded=False):
    for i, erro in enumerate(arquivo_atual.validacao["detalhes"]):
        st.write(f"{i+1}. {formatar_titulo_erro(erro.get('tipo'))}")

st.divider()

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
            st.rerun()
    
    if session_key_error in st.session_state:
        st.error(f"Falha na tentativa anterior: {st.session_state[session_key_error]}")
        st.warning("Verifique sua conexão ou tente novamente.")

    if ignorar_cache_flag:
        st.warning("Gerando nova solução pois a anterior (do cache) falhou na inserção.")

    if session_key_auto not in st.session_state:
        st.info("Necessário gerar correção via IA.")
    
    trigger_generation = False
    if session_key_auto in st.session_state:
        trigger_generation = True
        st.info("Gerando novo código automaticamente...")
    else:
        if st.button("Gerar Script de Correção", type="primary"):
            trigger_generation = True

    if trigger_generation:
        if session_key_error in st.session_state:
            del st.session_state[session_key_error]
        
        if session_key_auto in st.session_state:
            del st.session_state[session_key_auto]
            
        if f"ignore_cache_{arquivo_atual.id}" in st.session_state:
            del st.session_state[f"ignore_cache_{arquivo_atual.id}"]

        with st.spinner("IA analisando dados..."):
            try:
                codigo, usou_cache, hash_est, s_id, qtd, tokens, econ = gerar_codigo_correcao_ia(
                    arquivo_atual.df_original, 
                    arquivo_atual.validacao,
                    ignorar_cache=ignorar_cache_flag
                )
                
                st.session_state[session_key_code] = codigo
                st.session_state[session_key_meta] = {
                    "hash": hash_est,
                    "tokens": tokens,
                    "econ": econ,
                    "fonte": "IA",
                    "script_id": s_id
                }
                
                arquivo_atual.update_ia_stats(tokens, "IA", econ)
                st.rerun()
                
            except Exception as e:
                arquivo_atual.logger.registrar_erro("GERACAO_SCRIPT", "API Error", str(e))
                st.session_state[session_key_error] = str(e)
                st.rerun()

else:
    meta = st.session_state[session_key_meta]
    codigo_atual = st.session_state[session_key_code]
    
    if meta["fonte"] == "CACHE":
        vezes = meta.get("vezes_utilizado", 0)
        st.success(f"Código recuperado do CACHE. Verifique e execute. (Utilizado {vezes} vezes)")
    else:
        st.info("Código gerado pela IA. Verifique e execute.")
        
    st.code(codigo_atual, language="python")
    
    if session_key_exec not in st.session_state:
        
        c_exec, c_disc = st.columns([3, 1])
        
        with c_exec:
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
        
        with c_disc:
            if st.button("Descartar e Tentar Novamente", type="secondary", width='stretch'):
                del st.session_state[session_key_code]
                del st.session_state[session_key_meta]
                st.session_state[session_key_auto] = True
                if session_key_error in st.session_state: del st.session_state[session_key_error]
                st.rerun()
                
    else:
        df_temp = st.session_state[session_key_exec]
        res_valid = st.session_state.get(session_key_valid, {"valido": False})
        
        if res_valid["valido"]:
            st.success("Sucesso! Código executado e validação aprovada.")
        else:
            st.error(f"O código foi executado, mas a validação ainda encontrou {res_valid.get('total_erros', '?')} erro(s).")
            
        with st.expander("Ver Preview dos Dados", expanded=False):
            st.dataframe(df_temp.head())
        
        col_act1, col_act2 = st.columns([1, 1])
        
        with col_act1:
            if res_valid["valido"]:
                if st.button("Confirmar e Próximo", type="primary", width='stretch'):
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
                        arquivo_atual.update_ia_stats(0, "CACHE", meta["econ"])
                        arquivo_atual.script_id = meta.get("script_id")

                    del st.session_state[session_key_code]
                    del st.session_state[session_key_meta]
                    del st.session_state[session_key_exec]
                    if session_key_valid in st.session_state: del st.session_state[session_key_valid]
                    if session_key_error in st.session_state: del st.session_state[session_key_error]
                    st.rerun()
            else:
                 st.warning("Corrija os erros restantes gerando um novo script.")

        with col_act2:
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

button_col1, button_col2, button_col3 = st.columns(3)
if button_col1.button("Voltar para Lista", width='stretch'):
    st.switch_page("main.py")

if button_col3.button("Pular este arquivo (Marcar como Falha)", type="secondary", width='stretch'):
    arquivo_atual.status = "FALHA_MANUAL"
    
    arquivo_atual.logger.registrar_erro("GERACAO_SCRIPT", "Manual", "Usuario pulou o arquivo")
    
    if session_key_code in st.session_state: del st.session_state[session_key_code]
    if session_key_meta in st.session_state: del st.session_state[session_key_meta]
    if session_key_exec in st.session_state: del st.session_state[session_key_exec]
    if session_key_valid in st.session_state: del st.session_state[session_key_valid]
    if session_key_error in st.session_state: del st.session_state[session_key_error]
    if session_key_auto in st.session_state: del st.session_state[session_key_auto]
    
    st.rerun()