import streamlit as st
import pandas as pd
import tempfile
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.validation import (
    detectar_encoding,
    detectar_delimitador,
    validar_csv_completo
)

@st.cache_data
def carregar_template():
    with open("database/template.json", "r") as f:
        return json.load(f)

@st.cache_data(show_spinner="Processando arquivo...") 
def processar_arquivo(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp_file:
        tmp_file.write(uploaded_file.getbuffer())
        tmp_path = tmp_file.name

    try:
        encoding_detectado = detectar_encoding(tmp_path)
        delimitador_detectado = detectar_delimitador(tmp_path)
        
        # Otimização de leitura (apenas ler o necessário se o arquivo for gigante)
        df = pd.read_csv(tmp_path, encoding=encoding_detectado, sep=delimitador_detectado)
        
        template = carregar_template()
        resultado = validar_csv_completo(tmp_path, template)
        
        return df, encoding_detectado, delimitador_detectado, resultado
        
    finally:
        # Garante a limpeza do arquivo temporário
        if os.path.exists(tmp_path):
            os.remove(tmp_path)