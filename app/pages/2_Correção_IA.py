import streamlit as st
import pandas as pd
import json
from openai import OpenAI
from pathlib import Path
import sys
import os
from dotenv import load_dotenv
import tempfile

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                    
from src.validation import validar_csv_completo
from app.utils import formatar_titulo_erro
from app.services.script_cache import gerar_hash_estrutura, buscar_script_cache, salvar_script_cache
from app.services.database import init_database

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

# Gerar hash da estrutura do arquivo
colunas_df = list(df.columns)
hash_estrutura = gerar_hash_estrutura(colunas_df, resultado_validacao["detalhes"])

# Verificar se já existe script no cache
script_cache = buscar_script_cache(hash_estrutura)

if script_cache:
    # Script encontrado no cache
    st.success(f"Script encontrado no cache! (Utilizado {script_cache['vezes_utilizado']} vezes)")
    st.info("Economia: Chamada à IA evitada! Reutilizando script validado.")
    codigo_correcao = script_cache["script"]
    usou_cache = True
else:
    # Precisa gerar novo script com IA
    st.info("Gerando novo script com IA...")
    usou_cache = False

with st.spinner("Processando..." if script_cache else "IA analisando os erros e gerando código de correção..."):
    try:
        if not script_cache:
            # Só chama a IA se não encontrou no cache
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
        if usou_cache:
            st.caption("Script recuperado do cache")
        st.code(codigo_correcao, language="python")
        
        st.divider()
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.warning("Revise o código antes de executar!")
        with col2:
            exec_button = st.button("Executar Código", type="primary", use_container_width=True)
   
        if exec_button:
            try:
                df_corrigido = df.copy()
                
                namespace = {"df": df_corrigido, "pd": pd}
                exec(codigo_correcao, namespace)
                df_corrigido = namespace["df"]
                
                st.success("Código executado com sucesso!")
                
                st.subheader("Dados Corrigidos (10 primeiras linhas)")
                st.dataframe(df_corrigido.head(10))
                
                st.divider()

                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode='w', encoding='utf-8', newline='') as tmp:
                    df_corrigido.to_csv(tmp.name, index=False)
                    tmp_path = tmp.name
                
                try:
                    with open("database/template.json", "r") as f:
                        template_validacao = json.load(f)
                    
                    resultado_revalidacao = validar_csv_completo(tmp_path, template_validacao)
                    
                    if resultado_revalidacao["valido"]:
                        st.success("Validação concluída! O arquivo está correto e pronto para inserção no banco.")
                        
                        # Salvar script no cache apenas se não veio do cache e validação passou
                        if not usou_cache:
                            tipos_erros = [erro.get("tipo") for erro in resultado_validacao["detalhes"]]
                            salvar_script_cache(hash_estrutura, codigo_correcao, f"Corrige: {', '.join(tipos_erros)}")
                            st.info("Script validado e salvo no cache para uso futuro!")
                        
                        st.session_state["df_corrigido"] = df_corrigido
                        st.session_state["validacao_aprovada"] = True
                        
                        csv = df_corrigido.to_csv(index=False).encode('utf-8')


                        if st.button("Inserir no Banco de Dados", type="primary", use_container_width=True):
                            st.info("Funcionalidade de inserção no banco será implementada em breve.")

                    else:
                        st.error(f"Validação falhou! Ainda existem {resultado_revalidacao['total_erros']} erro(s).")
                        
                        st.subheader("Erros Restantes")
                        for i, erro in enumerate(resultado_revalidacao["detalhes"]):
                            st.write(f"{i+1}. {formatar_titulo_erro(erro.get('tipo'))}")

                        st.warning("Um novo ciclo de correção será necessário.")
                        
                        if st.button("Solicitar Nova Correção via IA", type="secondary"):
                            st.session_state["arquivo_erros"] = resultado_revalidacao
                            st.session_state["df_original"] = df_corrigido
                            st.rerun()
                
                finally:
                    os.remove(tmp_path)
                
            except Exception as e:
                st.error(f"Erro ao executar: {str(e)}")
        
    except Exception as e:
        st.error(f"Erro ao comunicar com a IA: {str(e)}")

st.divider()

col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if st.button("Voltar para Upload", use_container_width=True):
        st.switch_page("main.py")
with col3:
    if st.button("Limpar Dados", use_container_width=True):
        for key in ["arquivo_erros", "df_original", "df_corrigido", "encoding", "delimitador"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
