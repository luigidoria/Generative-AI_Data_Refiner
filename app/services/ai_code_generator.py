import streamlit as st
import json
import pandas as pd
from openai import OpenAI
from pathlib import Path
import os
from dotenv import load_dotenv
from app.services.auth_manager import AuthManager
from app.services.script_cache import gerar_hash_estrutura, buscar_script_cache
from app.utils.data_handler import carregar_template
from app.utils.ui_components import formatar_titulo_erro

def _construir_instrucoes_dinamicas(detalhes_erros):
    instrucoes_estrutura = []
    instrucoes_dados = []
    
    destinos_conflitantes = set()
    for erro in detalhes_erros:
        if erro.get("tipo") == "colunas_duplicadas":
            conflitos = erro.get("conflitos", {})
            destinos_conflitantes.update(conflitos.keys())

    for erro in detalhes_erros:
        tipo = erro.get("tipo")
        
        if tipo == "colunas_faltando":
            cols = erro.get("colunas", [])
            cols_str = ", ".join([f"'{c}'" for c in cols])
            instrucoes_estrutura.append(
                f"CRITICO - COLUNAS FALTANDO: O DataFrame NAO possui as colunas obrigatorias [{cols_str}]. "
                f"Voce DEVE cria-las explicitamente. Preencha com None (objeto Python nativo) para garantir compatibilidade com SQL. NAO use pd.NA."
            )
            
        elif tipo == "nomes_colunas":
            mapeamento = erro.get("mapeamento", {})
            mapeamento_seguro = {
                orig: dest for orig, dest in mapeamento.items() 
                if dest not in destinos_conflitantes
            }
            
            if mapeamento_seguro:
                instrucoes_estrutura.append(
                    f"RENOMEACAO: As colunas estao incorretas. Use examente este mapeamento no rename: {json.dumps(mapeamento_seguro)}. "
                    f"IMPORTANTE: Se uma coluna de destino ja existir no DF, remova-a (drop) ANTES de renomear para evitar colunas duplicadas com o mesmo nome."
                )
        
        elif tipo == "formato_valor":
            instrucoes_dados.append(
                "FORMATACAO DE VALOR: Identifique colunas monetarias (ex: com 'R$', pontos de milhar). "
                "Converta para float: remova 'R$', remova pontos, substitua virgula por ponto."
            )
            
        elif tipo == "formato_data":
            instrucoes_dados.append(
                "FORMATACAO DE DATA (CRITICO): Converta colunas de data para datetime. "
                "Use pd.to_datetime(..., format='mixed', dayfirst=True, errors='coerce'). " \
                "Depois converta para o formato 'YYYY-MM-DD' com .dt.strftime('%Y-%m-%d')."
            )
            
        elif tipo == "colunas_duplicadas":
            conflitos = erro.get("conflitos", {})
            resumo_conflitos = "; ".join([f"{origens} > '{dest}'" for dest, origens in conflitos.items()])
            
            instrucoes_estrutura.append(
                f"CONFLITO DE COLUNAS: Existem disputas de mapeamento: [{resumo_conflitos}]. "
                f"Resolva usando COALESCE: Mantenha os valores da coluna de destino como prioritarios. "
                f"Use as colunas de origem APENAS para preencher lacunas (fillna) na destino. "
                f"IMPORTANTE: NAO remova colunas extras no inicio do script se elas forem usadas aqui. "
                f"Ao final, remova as colunas de origem sobressalentes."
            )

    instrucoes = instrucoes_estrutura + instrucoes_dados

    if not instrucoes:
        instrucoes.append("Analise os dados e aplique as correcoes necessarias para adequar ao schema.")
        
    return "\n".join([f"{i+1}. {inst}" for i, inst in enumerate(instrucoes)])

def gerar_codigo_correcao_ia(df, resultado_validacao, ignorar_cache=False):
    colunas_df = list(df.columns)
    hash_estrutura = gerar_hash_estrutura(colunas_df, resultado_validacao["detalhes"])
    
    if not ignorar_cache:
        script_cache = buscar_script_cache(hash_estrutura)
        if script_cache:
            return (
                script_cache["script"],
                True,
                hash_estrutura,
                script_cache["id"],
                script_cache["vezes_utilizado"],
                0,
                script_cache.get("custo_tokens", 0)
            )
    
    auth = AuthManager()
    GROQ_API_KEY = auth.obter_api_key()
    
    if not GROQ_API_KEY:
        raise ValueError("API Key não encontrada! Configure o arquivo secrets.env")
    
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )
    
    template = carregar_template()
    
    instrucoes_especificas = _construir_instrucoes_dinamicas(resultado_validacao["detalhes"])
    
    sample_data = df.head(3).to_dict('records')
    dtypes_info = df.dtypes.to_string()
    
    historico_tentativas = ""
    if "script_anterior" in st.session_state and "erro_anterior" in st.session_state:
        historico_tentativas = f"""
        TENTATIVA ANTERIOR FALHOU COM O ERRO:
        {st.session_state['erro_anterior']}
        
        CODIGO QUE FALHOU:
        {st.session_state['script_anterior']}
        """

    prompt = f"""
    Voce e um Engenheiro de Dados Senior especialista em Pandas.
    Sua tarefa e gerar um script Python para corrigir um DataFrame chamado `df`.

    CONTEXTO DOS DADOS:
    - Colunas Atuais: {colunas_df}
    - Tipos de Dados (dtypes):
    {dtypes_info}
    - Amostra (head 3):
    {json.dumps(sample_data, indent=2, ensure_ascii=False)}

    {historico_tentativas}

    LISTA DE TAREFAS OBRIGATORIAS (Baseada nos erros detectados):
    {instrucoes_especificas}

    REGRAS GERAIS:
    1. Apenas remova colunas extras que nao estejam no template {list(template["colunas"].keys())} APOS realizar todas as correcoes de dados (merges, renames, etc), no final do script.
    2. O codigo deve assumir que 'df' e 'pd' ja existem.
    3. NAO use blocos markdown. Retorne apenas o codigo.
    4. Se precisar de regex, importe 're'. Se precisar de numpy, importe 'numpy as np'.
    5. GARANTIA FINAL: Apos todas as transformacoes, execute df = df.loc[:, ~df.columns.duplicated()] para garantir que nao existam colunas com nomes duplicados.
    6. A saida final deve ser a alteracao do dataframe `df`.

    Gere apenas o codigo Python:
    """
    
    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Voce gera apenas codigo Python puro, sem formatacao Markdown."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    tokens_gastos = 0
    codigo_correcao = chat_completion.choices[0].message.content
    codigo_correcao = codigo_correcao.replace("```python", "").replace("```", "").strip()

    if hasattr(chat_completion, 'usage') and chat_completion.usage:
        tokens_gastos = chat_completion.usage.total_tokens
    
    return (
        codigo_correcao,
        False,  
        hash_estrutura,
        None,
        0,
        tokens_gastos,
        0
    )

def new_correction(codigo_correcao, resultado_revalidacao, df_corrigido):
    st.session_state["script_anterior"] = codigo_correcao
    erros_detalhados = "\n".join([f"- {formatar_titulo_erro(e.get('tipo'))}" for e in resultado_revalidacao["detalhes"]])
    st.session_state["erro_anterior"] = f"Erros restantes após execução:\n{erros_detalhados}"
    
    st.session_state["arquivo_erros"] = resultado_revalidacao
    st.session_state["df_original"] = df_corrigido
    
    if "codigo_gerado" in st.session_state:
        del st.session_state["codigo_gerado"]
    if "usou_cache" in st.session_state:
        del st.session_state["usou_cache"]
    if "hash_estrutura" in st.session_state:
        del st.session_state["hash_estrutura"]
    
    st.rerun()