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

st.set_page_config(
    page_title="Franq | Ingestão de Dados",
    page_icon=":bar_chart:",
    layout="wide"
)

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

            st.write(f"**Arquivo carregado com sucesso!**")
            st.write(f"- Número de linhas: {qtd_linhas}")
            st.write(f"- Número de colunas: {qtd_colunas}")
            st.write(f"- Encoding detectado: {encoding_detectado}")
            st.write(f"- Delimitador detectado: '{delimitador_detectado}'")

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")
        
        finally:
            os.remove(tmp_path)