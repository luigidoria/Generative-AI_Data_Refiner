"""
Módulo para cache de scripts de correção baseado em similaridade.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional

def init_script_costs_table():
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS script_costs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_id INTEGER,
            custo_tokens INTEGER DEFAULT 0,
            FOREIGN KEY(script_id) REFERENCES scripts_transformacao(id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_costs_script_id ON script_costs(script_id)")
    
    conn.commit()
    conn.close()

def gerar_hash_estrutura(colunas: list, erros: list) -> str:
    colunas_ordenadas = sorted(colunas)
    
    tipos_erros = sorted([erro.get("tipo", "") for erro in erros])
    
    estrutura = {
        "colunas": colunas_ordenadas,
        "tipos_erros": tipos_erros
    }
    
    estrutura_json = json.dumps(estrutura, sort_keys=True, ensure_ascii=False)

    hash_obj = hashlib.md5(estrutura_json.encode('utf-8'))
    
    return hash_obj.hexdigest()


def buscar_script_cache(hash_estrutura: str) -> Optional[dict]:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    
    if not db_path.exists():
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT 
            s.id, 
            s.script_python, 
            s.vezes_utilizado,
            COALESCE(c.custo_tokens, 0) as custo_tokens
        FROM scripts_transformacao s
        LEFT JOIN script_costs c ON s.id = c.script_id
        WHERE s.hash_estrutura = ?
        """,
        (hash_estrutura,)
    )
    
    resultado = cursor.fetchone()
    
    if resultado:
        cursor.execute(
            """
            UPDATE scripts_transformacao 
            SET vezes_utilizado = vezes_utilizado + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (resultado["id"],)
        )
        conn.commit()
        
        script_info = {
            "id": resultado["id"],
            "script": resultado["script_python"],
            "vezes_utilizado": resultado["vezes_utilizado"] + 1,
            "custo_tokens": resultado["custo_tokens"]
        }
        conn.close()
        return script_info
    
    conn.close()
    return None

def salvar_script_cache(hash_estrutura: str, script: str, descricao: str = None, tokens: int = 0) -> int:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            INSERT INTO scripts_transformacao (hash_estrutura, script_python, descricao)
            VALUES (?, ?, ?)
            ON CONFLICT(hash_estrutura) DO UPDATE SET
                script_python = excluded.script_python,
                descricao = excluded.descricao,
                updated_at = CURRENT_TIMESTAMP
            """,
            (hash_estrutura, script, descricao)
        )
        
        cursor.execute("SELECT id FROM scripts_transformacao WHERE hash_estrutura = ?", (hash_estrutura,))
        script_id = cursor.fetchone()[0]
        
        cursor.execute(
            """
            INSERT INTO script_costs (script_id, custo_tokens)
            VALUES (?, ?)
            """,
            (script_id, tokens)
        )
        
        conn.commit()
        return script_id
    except Exception as e:
        print(f"Erro ao salvar script: {e}")
        return None
    finally:
        conn.close()