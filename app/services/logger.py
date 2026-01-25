import sqlite3
import hashlib
import streamlit as st
from datetime import datetime
from pathlib import Path

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
                usou_ia BOOLEAN DEFAULT FALSE,
                tokens_gastos INTEGER DEFAULT 0,
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