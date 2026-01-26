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
                status TEXT NOT NULL CHECK (status IN ('CONCLUIDO', 'FALHA', 'INTERROMPIDO', 'PENDENTE', 'CANCELADO', 'PROCESSANDO')),
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

def carregar_dados():
    try:
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT 
                id, arquivo_nome, origem_correcao, 
                tokens_gastos, tokens_economizados, tentativas_ia,
                registros_inseridos, registros_duplicados, registros_erros, status, 
                etapa_final, tipo_erro, mensagem_erro, duracao_segundos, created_at
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
    
class LogMonitoramento:
    def __init__(self, file_object):
        self.arquivo_bytes = file_object.getvalue()
        self.db_id = None
        self.dados = {
            "hash": hashlib.sha256(self.arquivo_bytes).hexdigest(),
            "nome": file_object.name,
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
            "mensagem_erro": None,
            "duracao": 0.0
        }
        
    def registrar_uso_ia(self, tokens, fonte, tokens_economizados=0):
        self.dados["tokens"] += tokens 
        self.dados["tokens_economizados"] += tokens_economizados
        self.dados["origem_correcao"] = fonte
        self.dados["etapa"] = "GERACAO_SCRIPT"
        if fonte == 'IA':
            self.dados["tentativas_ia"] += 1
        self._salvar_log_no_banco()

    def registrar_erro(self, etapa, tipo_erro, mensagem_erro):
        self.dados["etapa"] = etapa
        self.dados["status"] = "FALHA"
        self.dados["tipo_erro"] = str(tipo_erro)
        self.dados["mensagem_erro"] = str(mensagem_erro)[0:500]
        self.dados["duracao"] = (datetime.now() - self.dados["inicio"]).total_seconds()
        self._salvar_log_no_banco()

    def registrar_conclusao(self, inseridos, duplicados, erros):
        self.dados["etapa"] = "INGESTAO"
        self.dados["status"] = "CONCLUIDO"
        self.dados["inseridos"] = inseridos
        self.dados["duplicados"] = duplicados
        self.dados["erros"] = erros
        self.dados["duracao"] = (datetime.now() - self.dados["inicio"]).total_seconds()
        self._salvar_log_no_banco()

    def registrar_pendencia(self):
        self.dados["status"] = "PENDENTE"
        self.dados["duracao"] = (datetime.now() - self.dados["inicio"]).total_seconds()
        self._salvar_log_no_banco()

    def registrar_cancelamento(self):
        self.dados["status"] = "CANCELADO"
        self.dados["etapa"] = "REMOVIDO_PELO_USUARIO"
        self.dados["duracao"] = (datetime.now() - self.dados["inicio"]).total_seconds()
        self._salvar_log_no_banco()

    def _salvar_log_no_banco(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Se ainda não tem ID, faz INSERT
            if self.db_id is None:
                cursor.execute("""
                    INSERT INTO monitoramento_processamento 
                    (arquivo_hash, arquivo_nome, origem_correcao, tokens_gastos, tokens_economizados, tentativas_ia,
                    registros_inseridos, registros_duplicados, registros_erros, status, 
                    etapa_final, tipo_erro, mensagem_erro, duracao_segundos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.dados.get("hash"),
                    self.dados.get("nome"),
                    self.dados.get("origem_correcao", "NENHUMA"),
                    self.dados.get("tokens", 0),
                    self.dados.get("tokens_economizados", 0),
                    self.dados.get("tentativas_ia", 0),
                    self.dados.get("inseridos", 0),      
                    self.dados.get("duplicados", 0),  
                    self.dados.get("erros", 0),       
                    self.dados.get("status"),
                    self.dados.get("etapa"),
                    self.dados.get("tipo_erro"),
                    self.dados.get("mensagem_erro"),
                    self.dados.get("duracao", 0.0)
                ))
                # Captura o ID da linha recém criada e guarda na memória
                self.db_id = cursor.lastrowid
            
            # Se JÁ tem ID, faz UPDATE
            else:
                cursor.execute("""
                    UPDATE monitoramento_processamento SET
                        origem_correcao = ?,
                        tokens_gastos = ?,
                        tokens_economizados = ?,
                        tentativas_ia = ?,
                        registros_inseridos = ?,
                        registros_duplicados = ?,
                        registros_erros = ?,
                        status = ?,
                        etapa_final = ?,
                        tipo_erro = ?,
                        mensagem_erro = ?,
                        duracao_segundos = ?
                    WHERE id = ?
                """, (
                    self.dados.get("origem_correcao", "NENHUMA"),
                    self.dados.get("tokens", 0),
                    self.dados.get("tokens_economizados", 0),
                    self.dados.get("tentativas_ia", 0),
                    self.dados.get("inseridos", 0),      
                    self.dados.get("duplicados", 0),  
                    self.dados.get("erros", 0),       
                    self.dados.get("status"),
                    self.dados.get("etapa"),
                    self.dados.get("tipo_erro"),
                    self.dados.get("mensagem_erro"),
                    self.dados.get("duracao", 0.0),
                    self.db_id
                ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar log no banco: {e}")