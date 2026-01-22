import streamlit as st
import pandas as pd
import json
from openai import OpenAI
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.utils import formatar_titulo_erro

st.set_page_config(
    page_title="Franq | Correção IA",
    page_icon=":bar_chart:",
    layout="wide"
)

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Correção Automática via IA")
st.divider()

if "arquivo_erros" not in st.session_state or "df_original" not in st.session_state:
    st.warning("Nenhum arquivo com erros foi carregado!")
    st.info("Por favor, volte para a página principal e faça o upload de um arquivo CSV.")
    
    if st.button("Voltar para Upload", type="primary"):
        st.switch_page("main.py")
    st.stop()

resultado_validacao = st.session_state["arquivo_erros"]
df = st.session_state["df_original"]

st.subheader("Resumo dos Erros Detectados")

col1, col2, col3 = st.columns(3)
col1.metric("Total de Erros", resultado_validacao["total_erros"])
col2.metric("Linhas no Arquivo", len(df))
col3.metric("Status", "Necessita Correção")

st.divider()

if st.button("Voltar para a pagina de upload", type="primary"):
    st.switch_page("main.py")

st.subheader("Tipos de Erros Encontrados")

for i, erro in enumerate(resultado_validacao["detalhes"]):
    tipo_erro = erro.get("tipo")
    st.write(f"**{i+1}.** {formatar_titulo_erro(tipo_erro)}")
    
    if tipo_erro == 'nomes_colunas':
        mapeamento = erro.get("mapeamento", {})
        if mapeamento:
            st.caption(f"{len(mapeamento)} colunas com nomes diferentes")
    elif tipo_erro == 'formato_valor':
        formato = erro.get("formato_detectado", "Desconhecido")
        st.caption(f"Formato detectado: {formato}")
    elif tipo_erro == 'formato_data':
        formato = erro.get("formato_detectado", "Desconhecido")
        st.caption(f"Formato detectado: {formato}")
    elif tipo_erro == 'colunas_faltando':
        colunas = erro.get("colunas", [])
        st.caption(f"Faltam {len(colunas)} colunas obrigatórias")

st.divider()

st.subheader("Gerando Script de Correção")

with st.spinner("IA analisando os erros e gerando código de correção..."):
    try:
        env_path = Path(__file__).parent.parent / "secrets.env"
        load_dotenv(env_path)
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        
        if not GROQ_API_KEY:
            st.error("API Key não encontrada! Configure o arquivo secrets.env")
            st.stop()
        
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=GROQ_API_KEY
        )
        
        # Carregar template para obter colunas válidas
        with open("database/template.json", "r", encoding="utf-8") as f:
            template = json.load(f)
        
        # Extrair colunas válidas (incluindo aliases)
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
        
        # Identificar tipos de erros presentes
        tipos_erros = [erro.get("tipo") for erro in resultado_validacao["detalhes"]]
        
        erros_texto = json.dumps(resultado_validacao["detalhes"], indent=2, ensure_ascii=False)
        colunas_df = list(df.columns)
        sample_data = df.head(3).to_dict('records')
        
        prompt = f"""
                Você é um especialista em correção de dados com Python e Pandas.

                Analise os seguintes erros detectados em um arquivo CSV:

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
                   - Converter a coluna de data para YYYY-MM-DD usando pd.to_datetime().dt.strftime('%Y-%m-%d')
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
            temperature=0.3,
            max_tokens=2048,
        )
        
        codigo_correcao = chat_completion.choices[0].message.content
        
        codigo_correcao = codigo_correcao.replace("```python", "").replace("```", "").strip()
        
        st.success("Script de correção gerado com sucesso!")
        
        st.divider()
        st.subheader("Código de Correção")
        st.code(codigo_correcao, language="python")
        
        st.divider()

    except Exception as e:
        st.error(f"Erro ao comunicar com a IA: {str(e)}")