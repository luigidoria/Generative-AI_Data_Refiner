import streamlit as st
import pandas as pd

from services.database import init_database

from utils.ui_components import formatar_titulo_erro
from utils.session_manager import rest_all_states
from utils.data_handler import processar_arquivo
from services.logger import init_logger_table, iniciar_monitoramento

st.set_page_config(
    page_title="Franq | Ingestão de Dados",
    page_icon=":bar_chart:",
    layout="wide"
)

st.markdown("""
    <style>
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
""", unsafe_allow_html=True)

state_padroes = {
    "df": None,
    "encoding": None,
    "delimitador": None,
    "resultado_validacao": None,
    "nome_arquivo": None,
    "sem_modficadoes_necessarias": False,
    "banco_dados": False
}

for key, value in state_padroes.items():
    if key not in st.session_state:
        st.session_state[key] = value

if not st.session_state["banco_dados"]:
    init_database()
    init_logger_table()
    st.session_state["banco_dados"] = True


st.title("Portal de Ingestão de Transações")
st.divider()

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba o arquivo CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

    st.divider()
    if st.button("Ver Dashboard", use_container_width=True):
        st.session_state["pagina_anterior"] = "main.py"
        st.switch_page("pages/4_Dashboard.py")
    

container = st.container(border=True)
with container:
    st.markdown("### Upload de Arquivos")
    st.info("Faça o upload dos seus arquivos financeiros (CSV) para validação e correção automática via IA.")
    uploaded_file = st.file_uploader("Selecione o arquivo", type=["csv"], label_visibility="collapsed", on_change=rest_all_states, args=(state_padroes,))
    if (uploaded_file is not None or (
                st.session_state["df"] is not None 
                and st.session_state["encoding"] is not None 
                and st.session_state["delimitador"] is not None
                and st.session_state["nome_arquivo"] is not None 
                and st.session_state["resultado_validacao"] is not None)):
    
        st.divider()
        st.subheader("Estatísticas do Arquivo")
        
        st.session_state["sem_modficadoes_necessarias"] = False

        if uploaded_file is not None:
            if st.session_state["df"] is None:    
                iniciar_monitoramento(uploaded_file)
                try:
                    df, encoding_detectado, delimitador_detectado, resultado_validacao = processar_arquivo(uploaded_file)

                    st.session_state["df"] = df
                    st.session_state["encoding"] = encoding_detectado
                    st.session_state["delimitador"] = delimitador_detectado
                    st.session_state["nome_arquivo"] = uploaded_file.name
                    st.session_state["resultado_validacao"] = resultado_validacao
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo: {e}")
        if st.session_state["df"] is not None:
            df = st.session_state["df"]
            encoding_detectado = st.session_state["encoding"]
            delimitador_detectado = st.session_state["delimitador"]
            uploaded_file_name = st.session_state["nome_arquivo"]
            resultado_validacao = st.session_state["resultado_validacao"]
            qtd_linhas, qtd_colunas = df.shape
            st.info(f"Usando dados do arquivo {uploaded_file_name}.")


            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Linhas", qtd_linhas)
            m2.metric("Colunas", qtd_colunas)
            m3.metric("Delimitador", f"{delimitador_detectado}")
            m4.metric("Encoding", encoding_detectado)

            with st.expander("Visualizar Dados Brutos (Primeiras 5 linhas)", expanded=False):
                st.dataframe(df.head())

            st.subheader("Diagnóstico de Validação")
            if resultado_validacao["valido"]:
                st.success("O arquivo é válido e segue o padrão esperado!")
                button_insert = st.button("Iniciar Ingestão no Banco de Dados", type="primary")
                if button_insert:
                    st.session_state["df_corrigido"] = df
                    st.session_state["validacao_aprovada"] = True
                    st.session_state["sem_modficadoes_necessarias"] = True
                    st.switch_page("pages/3_Inserção_Banco.py")
            else:
                
                st.error(f"O arquivo contém {resultado_validacao['total_erros']} divergência(s) que precisam ser corrigidas.")
                
                st.divider()
                st.subheader("Relatório de Divergências")

                for i, erro in enumerate(resultado_validacao["detalhes"]):
                    
                    with st.expander(f"Erro #{i+1}: {formatar_titulo_erro(erro.get('tipo'))}", expanded=False):
                        
                        tipo_erro = erro.get("tipo")
                        if tipo_erro == 'nomes_colunas':
                            st.write("As colunas do arquivo não batem com o padrão esperado. O sistema identificou os seguintes nomes:")

                            mapeamento = erro.get("mapeamento", {})
                            if mapeamento:
                                df_map = pd.DataFrame(list(mapeamento.items()), columns=["Coluna no Arquivo", "Coluna Esperada (Padrão)"])
                                st.table(df_map)
                            else:
                                st.warning("Não foi possível sugerir um mapeamento automático.")

                        elif tipo_erro == 'formato_valor':
                            formato = erro.get("formato_detectado", "Desconhecido")
                            st.markdown(f"**Problema:** Os valores monetários estão em um formato não padronizado.")
                            st.markdown(f"**Detectado:** `{formato}` (Ex: 1.234,56)")
                            st.markdown(f"**Esperado:** `Decimal` (Ex: 1234.56)")

                        elif tipo_erro == 'formato_data':
                            formato = erro.get("formato_detectado", "Desconhecido")
                            st.markdown(f"**Problema:** As datas não estão no padrão do banco de dados.")
                            st.markdown(f"**Detectado:** `{formato}`")
                            st.markdown(f"**Esperado:** `YYYY-MM-DD`")

                        elif tipo_erro == 'colunas_faltando':
                            colunas = erro.get("colunas", [])
                            st.error(f"Estão faltando as seguintes colunas obrigatórias: {', '.join(colunas)}")

                        else:
                            st.write(erro)

                st.divider()
                if st.button("Solicitar Correção via IA", type="primary"):
                    st.session_state["arquivo_erros"] = resultado_validacao
                    st.session_state["df_original"] = df
                    st.switch_page("pages/2_Correção_IA.py")
