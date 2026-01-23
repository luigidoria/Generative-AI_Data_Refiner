import sqlite3
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any


def carregar_template() -> Dict:
    template_path = Path(__file__).parent.parent.parent / "database" / "template.json"
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalizar_status(valor: Any, template: Dict) -> str:
    if pd.isna(valor) or valor is None:
        return template['colunas']['status']['validacao'].get('default', 'PENDENTE')
    
    valor_normalizado = str(valor).upper().strip()
    mapeamento = template['colunas']['status']['validacao']['mapeamento']
    
    mapeamento_upper = {k.upper(): v for k, v in mapeamento.items()}
    valor_normalizado = mapeamento_upper.get(valor_normalizado, valor_normalizado)
    
    valores_permitidos = template['colunas']['status']['validacao']['valores_permitidos']
    if valor_normalizado not in valores_permitidos:
        return template['colunas']['status']['validacao'].get('default', 'PENDENTE')
    
    return valor_normalizado


def normalizar_tipo(valor: Any, template: Dict) -> str:
    if pd.isna(valor) or valor is None:
        return ''
    
    valor_normalizado = str(valor).upper().strip()
    mapeamento = template['colunas']['tipo']['validacao']['mapeamento']
    
    mapeamento_upper = {k.upper(): v for k, v in mapeamento.items()}
    return mapeamento_upper.get(valor_normalizado, valor_normalizado)


def normalizar_categoria(valor: Any, template: Dict) -> str:
    if pd.isna(valor) or valor is None:
        return ''
    
    valor_normalizado = str(valor).upper().strip()
    mapeamento = template['colunas']['categoria']['validacao']['mapeamento']
    
    mapeamento_upper = {k.upper(): v for k, v in mapeamento.items()}
    return mapeamento_upper.get(valor_normalizado, valor_normalizado)


def inserir_transacoes(df: pd.DataFrame) -> Dict:
    db_path = Path(__file__).parent.parent.parent / "database" / "transacoes.db"
    
    try:
        template = carregar_template()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id_transacao FROM transacoes_financeiras")
        ids_existentes = set(row[0] for row in cursor.fetchall())
        
        registros_inseridos = 0
        registros_duplicados = 0
        erros = []
        
        for index, row in df.iterrows():
            try:
                id_transacao = row['id_transacao']
                
                if id_transacao in ids_existentes:
                    registros_duplicados += 1
                    erros.append({
                        "linha": index + 1,
                        "id_transacao": id_transacao,
                        "erro": "ID de transação já existe no banco de dados (duplicado)"
                    })
                    continue
                
                status = normalizar_status(row.get('status'), template)
                tipo = normalizar_tipo(row.get('tipo'), template)
                categoria = normalizar_categoria(row.get('categoria'), template)
                
                cursor.execute(
                    """
                    INSERT INTO transacoes_financeiras 
                    (id_transacao, data_transacao, valor, tipo, categoria, 
                     descricao, conta_origem, conta_destino, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        id_transacao,
                        row['data_transacao'],
                        row['valor'],
                        tipo,
                        categoria,
                        row.get('descricao', None),
                        row['conta_origem'],
                        row.get('conta_destino', None),
                        status
                    )
                )
                registros_inseridos += 1
                ids_existentes.add(id_transacao)
                
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
            "registros_duplicados": registros_duplicados,
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
