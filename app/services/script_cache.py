"""
Módulo para cache de scripts de correção baseado em similaridade.
"""
import hashlib
import json


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
