import sqlite3
import hashlib
import streamlit as st
from datetime import datetime
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent.parent.parent / "database" / "transacoes.db"

def init_logger_table():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monitoramento_processamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                arquivo_hash TEXT NOT NULL,
                arquivo_nome TEXT NOT NULL,
                origem_correcao TEXT CHECK (origem_correcao IN ('IA', 'CACHE', 'NENHUMA')),
                tokens_gastos INTEGER DEFAULT 0,
                tokens_economizados INTEGER DEFAULT 0,
                tentativas_ia INTEGER DEFAULT 0,
                registros_inseridos INTEGER DEFAULT 0,
                registros_duplicados INTEGER DEFAULT 0,
                registros_erros INTEGER DEFAULT 0,       
                status TEXT NOT NULL CHECK (status IN ('CONCLUIDO', 'FALHA', 'INTERROMPIDO')),
                etapa_final TEXT,
                tipo_erro TEXT,
                mensagem_erro TEXT,
                duracao_segundos REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_hash ON monitoramento_processamento(arquivo_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_status ON monitoramento_processamento(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_data ON monitoramento_processamento(created_at)")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao inicializar tabela de logs: {e}")

def calcular_hash(bytes_arquivo):
    return hashlib.sha256(bytes_arquivo).hexdigest()


def salvar_log_no_banco(dados_log):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO monitoramento_processamento 
            (arquivo_hash, arquivo_nome, origem_correcao, tokens_gastos, tokens_economizados, tentativas_ia,
             registros_inseridos, registros_duplicados, registros_erros, status, 
             etapa_final, tipo_erro, mensagem_erro, duracao_segundos)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            dados_log.get("hash"),
            dados_log.get("nome"),
            dados_log.get("origem_correcao", "NENHUMA"),
            dados_log.get("tokens", 0),
            dados_log.get("tokens_economizados", 0),
            dados_log.get("tentativas_ia", 0),
            dados_log.get("inseridos", 0),      
            dados_log.get("duplicados", 0),  
            dados_log.get("erros", 0),       
            dados_log.get("status"),
            dados_log.get("etapa"),
            dados_log.get("tipo_erro"),
            dados_log.get("mensagem_erro"),
            dados_log.get("duracao", 0.0)
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar log no banco: {e}")

def atualizar_uso_ia(tokens, fonte, tokens_economizados=0):
    if "log_atual" in st.session_state:
        log = st.session_state["log_atual"]
        log["tokens"] = log.get("tokens", 0) + tokens
        log["tokens_economizados"] = log.get("tokens_economizados", 0) + tokens_economizados
        log["origem_correcao"] = fonte
        log["etapa"] = "GERACAO_SCRIPT"
        if fonte == 'IA':
            log["tentativas_ia"] = log.get("tentativas_ia", 0) + 1

def iniciar_monitoramento(uploaded_file):
    if "log_atual" in st.session_state:
        log_anterior = st.session_state["log_atual"]
        
        if log_anterior.get("status") == "PROCESSANDO":
            log_anterior["status"] = "INTERROMPIDO"
            log_anterior["duracao"] = (datetime.now() - log_anterior["inicio"]).total_seconds()
            
            salvar_log_no_banco(log_anterior)
    
    arquivo_bytes = uploaded_file.getvalue()
    arquivo_hash = calcular_hash(arquivo_bytes)
    
    st.session_state["log_atual"] = {
        "hash": arquivo_hash,
        "nome": uploaded_file.name,
        "inicio": datetime.now(),
        "origem_correcao": "NENHUMA",
        "tokens": 0,
        "tokens_economizados": 0,
        "tentativas_ia": 0,
        "inseridos": 0,
        "duplicados": 0,
        "erros": 0,
        "etapa": "UPLOAD",
        "status": "PROCESSANDO",
        "tipo_erro": None,
        "mensagem_erro": None
    }

def registrar_erro(etapa, tipo_erro, mensagem_erro):
    if "log_atual" in st.session_state:
        log = st.session_state["log_atual"]
        log["etapa"] = etapa
        log["status"] = "FALHA"
        log["tipo_erro"] = str(tipo_erro)
        log["mensagem_erro"] = str(mensagem_erro)[0:500] 
        log["duracao"] = (datetime.now() - log["inicio"]).total_seconds()
        
        salvar_log_no_banco(log)

        del st.session_state["log_atual"]

def registrar_conclusao(inseridos, duplicados, erros):
    if "log_atual" in st.session_state:
        log = st.session_state["log_atual"]
        log["etapa"] = "INGESTAO"
        log["status"] = "CONCLUIDO"
        log["inseridos"] = inseridos      
        log["duplicados"] = duplicados
        log["erros"] = erros     
        log["duracao"] = (datetime.now() - log["inicio"]).total_seconds()
        
        salvar_log_no_banco(log)
        
        del st.session_state["log_atual"]

def carregar_dados():

    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT 
                id, arquivo_nome, origem_correcao, 
                tokens_gastos, tokens_economizados, tentativas_ia,
                registros_inseridos, registros_duplicados, registros_erros, status, 
                etapa_final, tipo_erro, duracao_segundos, created_at
            FROM monitoramento_processamento
            ORDER BY created_at DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        
        df['created_at'] = pd.to_datetime(df['created_at'])
        return df
    except Exception as e:
        st.error(f"Erro ao conectar no banco: {e}")
        return pd.DataFrame()