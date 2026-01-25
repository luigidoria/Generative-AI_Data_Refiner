import streamlit as st
import pandas as pd
import json
from pathlib import Path
import sys
import os
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                    
from src.validation import validar_csv_completo
from app.utils.ui_components import formatar_titulo_erro
from app.services.script_cache import salvar_script_cache
from app.services.ai_code_generator import gerar_codigo_correcao_ia, new_correction
from app.utils.data_handler import carregar_template

st.set_page_config(
    page_title="Franq | Correção IA",
    page_icon=":bar_chart:",
    layout="wide"
)

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Correção Automática via IA")
st.divider()

if "arquivo_erros" not in st.session_state or "df_original" not in st.session_state:
    st.warning("Nenhum arquivo com erros foi carregado!")
    st.info("Por favor, volte para a página principal e faça o upload de um arquivo CSV.")
    
    if st.button("Voltar para Upload", type="primary"):
        st.switch_page("main.py")
    st.stop()

if "vezes_utilizado" not in st.session_state:
    st.session_state["vezes_utilizado"] = 0

resultado_validacao = st.session_state["arquivo_erros"]
df = st.session_state["df_original"]

st.subheader("Resumo dos Erros Detectados")

col1, col2, col3 = st.columns(3)
col1.metric("Total de Erros", resultado_validacao["total_erros"])
col2.metric("Linhas no Arquivo", len(df))
col3.metric("Status", "Necessita Correção")

st.divider()

st.subheader("Tipos de Erros Encontrados")

for i, erro in enumerate(resultado_validacao["detalhes"]):
    tipo_erro = erro.get("tipo")
    st.write(f"**{i+1}.** {formatar_titulo_erro(tipo_erro)}")
    
    if tipo_erro == 'nomes_colunas':
        mapeamento = erro.get("mapeamento", {})
        if mapeamento:
            st.caption(f"{len(mapeamento)} colunas com nomes diferentes")
    elif tipo_erro == 'formato_valor':
        formato = erro.get("formato_detectado", "Desconhecido")
        st.caption(f"Formato detectado: {formato}")
    elif tipo_erro == 'formato_data':
        formato = erro.get("formato_detectado", "Desconhecido")
        st.caption(f"Formato detectado: {formato}")
    elif tipo_erro == 'colunas_faltando':
        colunas = erro.get("colunas", [])
        st.caption(f"Faltam {len(colunas)} colunas obrigatórias")

st.divider()

st.subheader("Gerando Script de Correção")

if "codigo_gerado" not in st.session_state:
    st.info("Gerando script de correção...")
    with st.spinner("IA analisando os erros e gerando código de correção..."):
        try:
            codigo_correcao, usou_cache, hash_estrutura, script_id_cache, vezes_utilizado = gerar_codigo_correcao_ia(df, resultado_validacao)
            
            st.session_state["codigo_gerado"] = codigo_correcao
            st.session_state["usou_cache"] = usou_cache
            st.session_state["hash_estrutura"] = hash_estrutura
            st.session_state["vezes_utilizado"] = vezes_utilizado

            if usou_cache:
                st.session_state["script_id_cache"] = script_id_cache
                st.session_state["vezes_utilizado"] = vezes_utilizado
                st.success(f"Script encontrado no cache! Usado {vezes_utilizado} vezes.")
            else:
                st.success("Script de correção gerado com sucesso!")
                
        except Exception as e:
            st.error(f"Erro ao gerar código: {str(e)}")
            st.stop()
else:
    codigo_correcao = st.session_state["codigo_gerado"]
    usou_cache = st.session_state.get("usou_cache", False)
    hash_estrutura = st.session_state.get("hash_estrutura")
    
    if usou_cache:
        st.success(f"Script recuperado do cache! Usado {st.session_state.get('vezes_utilizado', 0)} vezes.")

st.divider()
st.subheader("Código de Correção")
if usou_cache:
    st.caption("Script recuperado do cache")
st.code(codigo_correcao, language="python")

st.divider()

if usou_cache:
    st.info("Executando script do cache automaticamente...")
    executar_script = True
else:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.warning("Revise o código antes de executar!")
    with col2:
        executar_script = st.button("Executar Código", type="primary", width='stretch')

if executar_script:
    try:
        df_corrigido = df.copy()
        
        namespace = {"df": df_corrigido, "pd": pd}
        exec(codigo_correcao, namespace)
        df_corrigido = namespace["df"]
        
        st.success("Código executado com sucesso!")
        
        st.subheader("Dados Corrigidos (10 primeiras linhas)")
        st.dataframe(df_corrigido.head(10))
        
        st.divider()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode='w', encoding='utf-8', newline='') as tmp:
            df_corrigido.to_csv(tmp.name, index=False)
            tmp_path = tmp.name
        
        try:
            
            template_validacao = carregar_template()
            
            resultado_revalidacao = validar_csv_completo(tmp_path, template_validacao)
            
            if resultado_revalidacao["valido"]:
                st.success("Validação concluída! O arquivo está correto e pronto para inserção no banco.")
                
                if not usou_cache:
                    tipos_erros = [erro.get("tipo") for erro in resultado_validacao["detalhes"]]
                    script_id = salvar_script_cache(hash_estrutura, codigo_correcao, f"Corrige: {', '.join(tipos_erros)}")
                    st.session_state["script_id_cache"] = script_id
                    st.info("Script validado e salvo no cache para uso futuro!")
                
                if "script_anterior" in st.session_state:
                    del st.session_state["script_anterior"]
                if "erro_anterior" in st.session_state:
                    del st.session_state["erro_anterior"]
                
                st.session_state["df_corrigido"] = df_corrigido
                st.session_state["validacao_aprovada"] = True

            else:
                if "validacao_aprovada" in st.session_state:
                    del st.session_state["validacao_aprovada"]
                
                st.error(f"Validação falhou! Ainda existem {resultado_revalidacao['total_erros']} erro(s).")
                
                st.subheader("Erros Restantes")
                for i, erro in enumerate(resultado_revalidacao["detalhes"]):
                    st.write(f"{i+1}. {formatar_titulo_erro(erro.get('tipo'))}")

                st.warning("Um novo ciclo de correção será necessário.")
                
                col_a, col_b, col_c = st.columns([1, 2, 1])
                with col_b:
                    st.button("Solicitar Nova Correção via IA", type="secondary", width='stretch', on_click=new_correction, args=(codigo_correcao, resultado_revalidacao, df_corrigido))
        
        finally:
            os.remove(tmp_path)
        
    except Exception as e:
        if "validacao_aprovada" in st.session_state:
            del st.session_state["validacao_aprovada"]
        
        st.error(f"Erro ao executar: {str(e)}")
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            st.button("Solicitar Nova Correção via IA", type="secondary", width='stretch', on_click=new_correction, args=(codigo_correcao, resultado_validacao, df))
                

if "validacao_aprovada" in st.session_state and st.session_state["validacao_aprovada"]:
    col_nav1, col_nav2, col_nav3 = st.columns([1, 1, 1])
    with col_nav2:
        if st.button("Inserir no Banco de Dados", type="primary", width='stretch', key="nav_insert"):
            st.switch_page("pages/3_Inserção_Banco.py")


st.divider()

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("Voltar para Upload", width='stretch'):
        st.switch_page("main.py")
