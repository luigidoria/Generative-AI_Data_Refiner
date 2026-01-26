import streamlit as st
import pandas as pd
from services.database import init_database
from utils.ui_components import formatar_titulo_erro
from utils.file_session import FileSession
from services.logger import init_logger_table
from services.script_cache import init_script_costs_table

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

if "banco_dados" not in st.session_state:
    init_database()
    init_logger_table()
    init_script_costs_table()
    st.session_state["banco_dados"] = True

if "fila_arquivos" not in st.session_state:
    st.session_state["fila_arquivos"] = []

def remover_arquivo(indice):
    arquivo = st.session_state["fila_arquivos"][indice]
    arquivo.cancelar()
    st.session_state["fila_arquivos"].pop(indice)

st.title("Portal de Ingestão de Transações")
st.divider()

with st.sidebar:
    st.markdown("""
    **Como funciona:**
    1. Suba os arquivos CSV.
    2. O sistema valida os dados.
    3. A IA corrige erros automaticamente.
    4. Dados corrigidos são inseridos no banco.
    """)

    st.divider()
    if st.button("Ver Dashboard", width='stretch'):
        st.session_state["pagina_anterior"] = "main.py"
        st.switch_page("pages/4_Dashboard.py")

container = st.container(border=True)
with container:
    st.markdown("### Upload de Arquivos")
    st.info("Faça o upload dos seus arquivos financeiros (CSV) para validação e correção automática via IA.")
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos", 
        type=["csv"], 
        label_visibility="collapsed", 
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("Processar e Adicionar à Fila", type="primary"):
            bar_progress = st.progress(0, text="Iniciando análise...")
            
            for i, arquivo in enumerate(uploaded_files):
                bar_progress.progress((i + 1) / len(uploaded_files), text=f"Validando {arquivo.name}...")
                
                try:
                    session = FileSession(arquivo, len(st.session_state["fila_arquivos"]) + i)
                    session.processar()
                    st.session_state["fila_arquivos"].append(session)
                    
                except Exception as e:
                    st.error(f"Erro ao processar {arquivo.name}: {e}")
            
            bar_progress.empty()
            st.rerun()

if st.session_state["fila_arquivos"]:
    st.divider()
    
    total = len(st.session_state["fila_arquivos"])
    pendentes = len([f for f in st.session_state["fila_arquivos"] if "PENDENTE" in f.status])
    prontos = total - pendentes
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total na Fila", total)
    c2.metric("Prontos", prontos)
    c3.metric("Pendentes", pendentes)
    
    st.subheader("Fila de Processamento")
    
    h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
    h1.markdown("**Arquivo**")
    h2.markdown("**Status**")
    h3.markdown("**Detalhes**")
    h4.markdown("**Ação**")
    
    st.divider()
    
    for idx, item in enumerate(st.session_state["fila_arquivos"]):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        
        c1.text(item.nome)
        
        if item.status == "PRONTO_VALIDO":
            c2.success("Valido")
        elif "PRONTO" in item.status:
            c2.info("Corrigido")
        elif item.status == "FALHA_MANUAL":
            c2.error("Falha Ignorada")
        else:
            c2.warning("Requer Correcao")
            
        if item.validacao["valido"]:
            c3.caption("OK")
        else:
            c3.error(f"{item.validacao['total_erros']} erros")
            
        with c4.popover("Remover"):
            st.write(f"Remover {item.nome}?")
            st.button(
                "Confirmar", 
                key=f"btn_rm_{idx}",
                on_click=remover_arquivo,
                args=(idx,)
            )

    st.divider()

    st.subheader("Detalhes dos Arquivos")
    
    nomes_abas = [item.nome for item in st.session_state["fila_arquivos"]]
    if nomes_abas:
        abas = st.tabs(nomes_abas)

        for aba, item in zip(abas, st.session_state["fila_arquivos"]):
            with aba:
                st.info(f"Usando dados do arquivo {item.nome}.")

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Linhas", item.df_original.shape[0])
                m2.metric("Colunas", item.df_original.shape[1])
                m3.metric("Delimitador", str(item.delimitador))
                m4.metric("Encoding", item.encoding)

                with st.expander("Visualizar Dados Brutos (Primeiras 5 linhas)", expanded=False):
                    st.dataframe(item.df_original.head())

                st.subheader("Diagnóstico de Validação")
                if item.validacao["valido"]:
                    st.success("O arquivo é válido e segue o padrão esperado!")
                else:
                    st.error(f"O arquivo contém {item.validacao['total_erros']} divergência(s) que precisam ser corrigidas.")
                    
                    st.divider()
                    st.subheader("Relatório de Divergências")

                    for i, erro in enumerate(item.validacao["detalhes"]):
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

    col_nav1, col_nav2 = st.columns([3, 1])
    
    with col_nav2:
        if pendentes > 0:
            if st.button("Ir para Correção", type="primary", width='stretch'):
                st.session_state["indice_atual"] = 0
                st.switch_page("pages/2_Correção_IA.py")
        
        elif total > 0:
            if st.button("Ir para Inserção", type="primary", width='stretch'):
                st.switch_page("pages/3_Inserção_Banco.py")