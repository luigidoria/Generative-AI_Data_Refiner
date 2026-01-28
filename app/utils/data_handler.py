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
    validar_csv_completo,
    validar_enum
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
        
        df = pd.read_csv(tmp_path, encoding=encoding_detectado, sep=delimitador_detectado)
        
        template = carregar_template()
        resultado = validar_csv_completo(tmp_path, template)
        erros_duplicata = detectar_colisoes_validacao(df, resultado)
        erros_enum = detectar_erros_enum(df, template, resultado)

        if erros_duplicata:
            resultado["valido"] = False
            resultado["detalhes"].extend(erros_duplicata)
    
        if erros_enum:
            resultado["valido"] = False
            resultado["detalhes"].extend(erros_enum)
            
        resultado["total_erros"] = len(resultado["detalhes"])
        
        return df, encoding_detectado, delimitador_detectado, resultado
        
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def detectar_colisoes_validacao(df: pd.DataFrame, resultado_validacao: dict) -> list:
    if "erro_leitura" in [e["tipo"] for e in resultado_validacao.get("detalhes", [])]:
        return []

    erro_nomes = next((e for e in resultado_validacao.get("detalhes", []) if e["tipo"] == "nomes_colunas"), None)
    
    if not erro_nomes or "mapeamento" not in erro_nomes:
        return []

    mapeamento = erro_nomes["mapeamento"] 
    colunas_existentes = set(df.columns)
    
    mapa_destino_origens = {}

    for origem, destino in mapeamento.items():
        if destino not in mapa_destino_origens:
            mapa_destino_origens[destino] = []
        
            if destino in colunas_existentes:
                mapa_destino_origens[destino].append(destino)
        
        mapa_destino_origens[destino].append(origem)

    conflitos = {
        dest: origs 
        for dest, origs in mapa_destino_origens.items() 
        if len(origs) > 1
    }

    erros_extras = []
    
    if conflitos:
        erros_extras.append({
            "tipo": "colunas_duplicadas",
            "conflitos": conflitos,
            "mensagem": "Múltiplas colunas referem-se ao mesmo campo final."
        })

    return erros_extras

def detectar_erros_enum(df: pd.DataFrame, template: dict, resultado_validacao: dict) -> list:
    erros_enum = []
    mapa_colunas = {}
    for erro in resultado_validacao.get("detalhes", []):
        if erro.get("tipo") == "nomes_colunas":
            for origem, destino in erro.get("mapeamento", {}).items():
                if destino not in mapa_colunas:
                    mapa_colunas[destino] = []
                mapa_colunas[destino].append(origem)

    for col_template, config in template["colunas"].items():
        if "validacao" in config and "valores_permitidos" in config["validacao"]:
            
            candidatos = []
            
            if col_template in df.columns:
                candidatos.append(col_template)
            
            if col_template in mapa_colunas:
                for origem in mapa_colunas[col_template]:
                    if origem in df.columns and origem != col_template:
                        candidatos.append(origem)
            
            candidatos = list(dict.fromkeys(candidatos))
            
            for col_real in candidatos:
                if col_real != col_template:
                    df_temp = df[[col_real]].rename(columns={col_real: col_template})
                    resultado = validar_enum(df_temp, col_template, template)
                else:
                    resultado = validar_enum(df, col_template, template)
                
                if not resultado["valido"]:
                    erros_enum.append({
                        "tipo": "valores_invalidos",
                        "coluna": col_template,
                        "coluna_origem": col_real,
                        "valores_invalidos": resultado["valores_invalidos"],
                        "mapeamento_sugerido": resultado["mapeamento_sugerido"],
                        "valores_permitidos": config["validacao"]["valores_permitidos"],
                        "default": config["validacao"].get("default")
                    })
    
    return erros_enum