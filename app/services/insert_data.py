import sqlite3
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any
from app.utils.data_handler import carregar_template

def normalizar_valor(valor: Any, tipo_coluna: str, template: Dict) -> str:
    if pd.isna(valor) or valor is None:
        if tipo_coluna == 'status':
            return template['colunas']['status']['validacao'].get('default', 'PENDENTE')
        return ''
    
    valor_normalizado = str(valor).upper().strip()
    
    config = template['colunas'].get(tipo_coluna, {}).get('validacao', {})
    mapeamento = config.get('mapeamento', {})
    
    mapeamento_upper = {k.upper(): v for k, v in mapeamento.items()}
    valor_final = mapeamento_upper.get(valor_normalizado, valor_normalizado)
    
    if tipo_coluna == 'status':
        valores_permitidos = config.get('valores_permitidos', [])
        if valor_final not in valores_permitidos:
            return config.get('default', 'PENDENTE')
            
    return valor_final

def inserir_transacoes(df: pd.DataFrame) -> Dict:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    conn = None
    
    template = carregar_template()
        
    try:
        df["id_transacao"] = df["id_transacao"].astype(str).str.strip()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        ids_transacao = df['id_transacao'].astype(str).tolist()
        placeholders = ','.join(['?'] * len(ids_transacao))
        
        query_check = f"SELECT id_transacao FROM transacoes_financeiras WHERE id_transacao IN ({placeholders})"
        cursor.execute(query_check, ids_transacao)
        
        ids_existentes = set(row[0] for row in cursor.fetchall())
        
        novos_registros = []
        erros = []
        registros_duplicados = 0
        
        for index, row in df.iterrows():
            id_transacao = row['id_transacao']
            if id_transacao in ids_existentes:
                    registros_duplicados += 1
                    erros.append({
                        "linha": index + 1,
                        "id_transacao": id_transacao,
                        "erro": "ID duplicado (já existe no banco)"
                    })
                    continue
            try:             
                dados_tupla = (
                    id_transacao,
                    row['data_transacao'],
                    float(row['valor']),
                    normalizar_valor(row.get('tipo'), 'tipo', template),
                    normalizar_valor(row.get('categoria'), 'categoria', template),
                    row.get('descricao', None),
                    row['conta_origem'],
                    row.get('conta_destino', None),
                    normalizar_valor(row.get('status'), 'status', template)
                )
                novos_registros.append(dados_tupla)
                
            except Exception as e:
                erros.append({
                    "linha": index + 1,
                    "id_transacao": id_transacao,
                    "erro": str(e)
                })
        
        if novos_registros:
            cursor.executemany(
                """
                INSERT INTO transacoes_financeiras 
                (id_transacao, data_transacao, valor, tipo, categoria, 
                 descricao, conta_origem, conta_destino, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                novos_registros
            )
            conn.commit()
        
        return {
            "sucesso": True, 
            "registros_inseridos": len(novos_registros),
            "registros_duplicados": registros_duplicados,
            "total_registros": len(df),
            "erros": erros
        }
        
    except Exception as e:
        if conn:
            conn.rollback()
        
        return {
            "sucesso": False,
            "registros_inseridos": 0,
            "registros_duplicados": 0,
            "total_registros": len(df),
            "erros": [{"erro": f"Erro fatal no banco: {str(e)}"}]
        }
    
    finally:
        if conn:
            conn.close()

def registrar_log_ingestao(arquivo_nome: str, registros_total: int, registros_sucesso: int, registros_erro: int,
                           usou_ia: bool, script_id: int = None, duracao_segundos: float = 0.0) -> bool:
    
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    conn = None
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO log_ingestao 
            (arquivo_nome, registros_total, registros_sucesso, registros_erro, 
             usou_ia, script_id, duracao_segundos)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                arquivo_nome,
                registros_total,
                registros_sucesso,
                registros_erro,
                usou_ia,
                script_id,
                duracao_segundos
            )
        )
        
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Erro ao registrar log de ingestão: {e}")
        return False
        
    finally:
        if conn:
            conn.close()
