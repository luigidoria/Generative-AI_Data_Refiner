import streamlit as st
import json
import pandas as pd
from openai import OpenAI
from pathlib import Path
import os
from dotenv import load_dotenv
from app.services.script_cache import gerar_hash_estrutura, buscar_script_cache
from app.utils import formatar_titulo_erro, carregar_template


def gerar_codigo_correcao_ia(df, resultado_validacao):
    colunas_df = list(df.columns)
    hash_estrutura = gerar_hash_estrutura(colunas_df, resultado_validacao["detalhes"])
    
    script_cache = buscar_script_cache(hash_estrutura)
    
    if script_cache:
        return (
            script_cache["script"],
            True,
            hash_estrutura,
            script_cache["id"],
            script_cache["vezes_utilizado"]
        )
    
    env_path = Path(__file__).parent.parent / "secrets.env"
    load_dotenv(env_path)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    
    if not GROQ_API_KEY:
        raise ValueError("API Key não encontrada! Configure o arquivo secrets.env")
    
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=GROQ_API_KEY
    )
    
    template = carregar_template()
    
    colunas_validas = []
    for nome_col, config in template["colunas"].items():
        colunas_validas.append(nome_col)
        colunas_validas.extend(config.get("aliases", []))
    
    colunas_obrigatorias = [
        nome for nome, config in template["colunas"].items()
        if config.get("obrigatorio", False)
    ]
    
    colunas_opcionais = [
        nome for nome, config in template["colunas"].items()
        if not config.get("obrigatorio", False)
    ]
    
    erros_texto = json.dumps(resultado_validacao["detalhes"], indent=2, ensure_ascii=False)
    sample_data = df.head(3).to_dict('records')
    
    # Importar streamlit apenas para acessar session_state
    historico_tentativas = ""
    if "script_anterior" in st.session_state and "erro_anterior" in st.session_state:
        historico_tentativas = f"""
        **ATENÇÃO - TENTATIVA ANTERIOR FALHOU:**
        
        O script abaixo foi gerado anteriormente mas causou erro na validação:
        
        ```python
        {st.session_state['script_anterior']}
        ```
        
        **Erro que ocorreu:**
        {st.session_state['erro_anterior']}
        
        **IMPORTANTE:** NÃO repita o mesmo erro! Analise o que deu errado e corrija a abordagem.
        """

    prompt = f"""
        Você é um especialista em correção de dados com Python e Pandas.

        Analise os seguintes erros detectados em um arquivo CSV:
        
        {historico_tentativas}

        **Erros Detectados:**
        {erros_texto}

        **Colunas Atuais no DataFrame:**
        {colunas_df}

        **Colunas Válidas do Banco de Dados:**
        - Obrigatórias: {colunas_obrigatorias}
        - Opcionais: {colunas_opcionais}
        - Todos os aliases aceitos: {colunas_validas}

        **Amostra dos Dados (3 primeiras linhas):**
        {json.dumps(sample_data, indent=2, ensure_ascii=False)}

        **Tarefa:**
        Gere um script Python que corrija APENAS os erros listados acima. Siga estas regras:
        
        **SEMPRE EXECUTAR (independente dos erros):**
        1. Remover colunas EXTRAS (que não estão na lista de colunas válidas)
        2. Remover colunas DUPLICADAS (manter apenas a primeira ocorrência)
        
        **CORRIGIR APENAS SE O ERRO FOI DETECTADO:**
        
        3. SE houver erro "nomes_colunas":
           - Renomear colunas usando o mapeamento fornecido (use df.rename())
        
        4. SE houver erro "formato_data":
           - Converter a coluna de data para YYYY-MM-DD
           - Use pd.to_datetime() com parâmetros flexíveis para detectar formato automaticamente
           - Exemplo: df['data_transacao'] = pd.to_datetime(df['data_transacao'], format='mixed', dayfirst=True).dt.strftime('%Y-%m-%d')
           - O parâmetro format='mixed' permite múltiplos formatos
           - O parâmetro dayfirst=True interpreta 17-01-2024 como dia-mês-ano
           - SE NÃO houver este erro, NÃO ALTERE a coluna de data
        
        5. SE houver erro "formato_valor":
           - Converter valores monetários: remover R$, pontos de milhares, trocar vírgula por ponto
           - Usar: df['valor'].astype(str).str.replace('R$', '', regex=False).str.strip().str.replace('.', '', regex=False).str.replace(',', '.').astype(float)
           - SE NÃO houver este erro, NÃO ALTERE a coluna de valores
        
        6. SE houver erro "colunas_faltando":
           - Adicionar colunas obrigatórias faltantes com None

        **CRÍTICO:**
        - NÃO converta formatos que já estão corretos
        - NÃO altere colunas que não têm erros reportados
        - Corrija SOMENTE o que está listado nos erros detectados
        - SEMPRE remova colunas extras e duplicadas (isso é obrigatório)

        **IMPORTANTE:**
        - Retorne APENAS o código Python, sem explicações ou comentários
        - O código receberá uma variável chamada 'df' que já contém os dados carregados
        - Use 'df = df.operacao()' para que as modificações sejam salvas
        - Não use print() no final
        - Não use markdown code blocks (```), apenas o código puro
        - Não importe pandas novamente, ele já está disponível como 'pd'
        """
    
    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Você é um especialista em Python e Pandas. Gere apenas código limpo e funcional que modifique o DataFrame."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.5,
        max_tokens=2048,
    )
    
    codigo_correcao = chat_completion.choices[0].message.content
    codigo_correcao = codigo_correcao.replace("```python", "").replace("```", "").strip()
    
    return (
        codigo_correcao,
        False,  
        hash_estrutura,
        None,
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