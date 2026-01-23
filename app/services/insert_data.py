import sqlite3
import pandas as pd
from pathlib import Path
from typing import Dict


def inserir_transacoes(df: pd.DataFrame) -> Dict:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        registros_inseridos = 0
        erros = []
        
        # Inserir cada linha
        for index, row in df.iterrows():
            try:
                # Normalizar status
                status = row.get('status', 'PENDENTE')
                if pd.isna(status) or status is None:
                    status = 'PENDENTE'
                else:
                    status = str(status).upper().strip()
                    if status not in ('PENDENTE', 'CONCLUIDA', 'CANCELADA'):
                        status = 'PENDENTE'
                
                cursor.execute(
                    """
                    INSERT INTO transacoes_financeiras 
                    (id_transacao, data_transacao, valor, tipo, categoria, 
                     descricao, conta_origem, conta_destino, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row['id_transacao'],
                        row['data_transacao'],
                        row['valor'],
                        row['tipo'],
                        row['categoria'],
                        row.get('descricao', None),
                        row['conta_origem'],
                        row.get('conta_destino', None),
                        status
                    )
                )
                registros_inseridos += 1
            except Exception as e:
                erros.append({
                    "linha": index + 1,
                    "id_transacao": row.get('id_transacao', 'N/A'),
                    "erro": str(e)
                })
        
        conn.commit()
        conn.close()
        
        return {
            "sucesso": len(erros) == 0,
            "registros_inseridos": registros_inseridos,
            "total_registros": len(df),
            "erros": erros
        }
        
    except Exception as e:
        return {
            "sucesso": False,
            "registros_inseridos": 0,
            "total_registros": len(df),
            "erros": [{"erro": f"Erro geral: {str(e)}"}]
        }
