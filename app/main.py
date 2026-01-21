import streamlit as st
import pandas as pd
import os
import tempfile
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation import (
    detectar_encoding,
    detectar_delimitador,
    validar_csv_completo
)

from utils import formatar_titulo_erro

st.set_page_config(
    page_title="Franq | Ingestão de Dados",
    page_icon=":bar_chart:",
    layout="wide"
)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Portal de Ingestão de Transações")
st.divider()

with st.sidebar:
    st.header("Configurações")
    st.caption("Sistema de Ingestão v1.0")
    st.divider()
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

container = st.container(border=True)
with container:
    st.markdown("### Upload de Arquivos")
    st.info("Faça o upload dos seus arquivos financeiros (CSV) para validação e correção automática via IA.")
    uploaded_file = st.file_uploader("Selecione o arquivo", type=["csv"], label_visibility="collapsed")
    if uploaded_file is not None:

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            tmp_path = tmp_file.name

        try:
            encoding_detectado = detectar_encoding(tmp_path)
            delimitador_detectado = detectar_delimitador(tmp_path)

            df = pd.read_csv(tmp_path, encoding=encoding_detectado, sep=delimitador_detectado)
            qtd_linhas, qtd_colunas = df.shape

            with open("database/template.json", "r") as f:
                template_validacao = json.load(f)
            
            resultado_validacao = validar_csv_completo(tmp_path, template_validacao)

            st.divider()
            st.subheader("Estatísticas do Arquivo")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Linhas", qtd_linhas)
            m2.metric("Colunas", qtd_colunas)
            m3.metric("Delimitador", f"{delimitador_detectado}")
            m4.metric("Encoding", encoding_detectado)

            with st.expander("Visualizar Dados Brutos (Primeiras 5 linhas)", expanded=False):
                st.dataframe(df.head())

            st.subheader("Diagnóstico de Validação")
            if resultado_validacao["valido"]:
                st.success("O arquivo é válido e segue o padrão esperado!")
                st.button("Iniciar Ingestão no Banco de Dados", type="primary")
            else:
                
                st.error(f"O arquivo contém {resultado_validacao['total_erros']} divergência(s) que precisam ser corrigidas.")
                
                st.divider()
                st.subheader("Relatório de Divergências")

                for i, erro in enumerate(resultado_validacao["detalhes"]):
                    
                    with st.expander(f"Erro #{i+1}: {formatar_titulo_erro(erro.get('tipo'))}", expanded=False):
                        
                        tipo_erro = erro.get("tipo")
                        if tipo_erro == 'nomes_colunas':
                            st.write("As colunas do arquivo não batem com o padrão esperado. O sistema identificou os seguintes nomes:")

                            mapeamento = erro.get("mapeamento", {})
                            if mapeamento:
                                df_map = pd.DataFrame(list(mapeamento.items()), columns=["Coluna no Arquivo", "Coluna Esperada (Padrão)"])
                                st.table(df_map)
                            else:
                                st.warning("Não foi possível sugerir um mapeamento automático.")

                        elif tipo_erro == 'formato_valor':
                            formato = erro.get("formato_detectado", "Desconhecido")
                            st.markdown(f"**Problema:** Os valores monetários estão em um formato não padronizado.")
                            st.markdown(f"**Detectado:** `{formato}` (Ex: 1.234,56)")
                            st.markdown(f"**Esperado:** `Decimal` (Ex: 1234.56)")

                        elif tipo_erro == 'formato_data':
                            formato = erro.get("formato_detectado", "Desconhecido")
                            st.markdown(f"**Problema:** As datas não estão no padrão do banco de dados.")
                            st.markdown(f"**Detectado:** `{formato}`")
                            st.markdown(f"**Esperado:** `YYYY-MM-DD`")

                        elif tipo_erro == 'colunas_faltando':
                            colunas = erro.get("colunas", [])
                            st.error(f"Estão faltando as seguintes colunas obrigatórias: {', '.join(colunas)}")

                        else:
                            st.write(erro)

                st.divider()
                st.button("Solicitar Correção via IA", type="primary")

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
        
        finally:
            os.remove(tmp_path)