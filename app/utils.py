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


def formatar_titulo_erro(tipo_erro):
    titulos = {
        'nomes_colunas': 'Nomes das Colunas Incorretos',
        'formato_valor': 'Formato de Valor Monetário Inválido',
        'formato_data': 'Formato de Data Inválido',
        'colunas_faltando': 'Colunas Obrigatórias Ausentes'
    }
    return titulos.get(tipo_erro, 'Erro de Validação')

def rest_all_states(state_padroes):
    db_status = st.session_state.get("banco_dados", False)
    st.session_state.clear()
    st.session_state["banco_dados"] = db_status
    for key, value in state_padroes.items():
        if key != "banco_dados":
            st.session_state[key] = value

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