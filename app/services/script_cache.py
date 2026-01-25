"""
Módulo para cache de scripts de correção baseado em similaridade.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Optional


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
        "SELECT id, script_python, vezes_utilizado FROM scripts_transformacao WHERE hash_estrutura = ?",
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
            "vezes_utilizado": resultado["vezes_utilizado"] + 1
        }
        conn.close()
        return script_info
    
    conn.close()
    return None


def salvar_script_cache(hash_estrutura: str, script: str, descricao: str = None) -> int:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO scripts_transformacao (hash_estrutura, script_python, descricao)
        VALUES (?, ?, ?)
        """,
        (hash_estrutura, script, descricao)
    )
    
    script_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return script_id
