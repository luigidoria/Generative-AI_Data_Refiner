import streamlit as st
import pandas as pd
import time
from services.database import init_database
from utils.ui_components import formatar_titulo_erro, renderizar_cabecalho, configurar_estilo_visual
from utils.file_session import FileSession
from services.logger import init_logger_table
from services.script_cache import init_script_costs_table
from services.auth_manager import AuthManager

st.set_page_config(
    page_title="Ingestão de Dados",
    layout="wide"
)

configurar_estilo_visual()

auth = AuthManager()
auth.verificar_autenticacao()

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

with st.sidebar:
    st.header("Navegação")
    
    if st.button("Dashboard", width='stretch'):
        st.session_state["origem_dashboard"] = "main.py"
        st.switch_page("pages/4_Dashboard.py")
        
    if st.button("Configurações", width='stretch'):
        st.session_state["origem_config"] = "main.py" 
        st.switch_page("pages/9_Configuracoes.py")

    st.divider()
    st.caption("Faça o upload dos arquivos CSV para iniciar o fluxo de validação e correção.")

renderizar_cabecalho(1, "Gerencie o upload e processamento de arquivos financeiros.")


col_texto, col_modelo = st.columns([3, 1])

with col_texto:
    st.markdown("### Upload de Arquivos")
    st.markdown("O sistema aceita arquivos CSV. Certifique-se de que os dados sigam o padrão da empresa.")

with col_modelo:
    csv_exemplo = """id_transacao,data_transacao,valor,tipo,categoria,descricao,conta_origem,conta_destino,status
TRX-876-2025,2025-10-20,700.50,CREDITO,ACADEMIA,Mensalidade outubro,CC-19555,,CONFIRMADO
TRX-877-2025,2025-10-23,89.90,DEBITO,LIVRARIA,Livro de dados,CC-19555,,CONFIRMADO"""
    
    st.download_button(
        label="Baixar Planilha Modelo",
        data=csv_exemplo,
        file_name="modelo_importacao.csv",
        mime="text/csv",
        width='stretch',
        help="Baixe este arquivo para ver quais colunas são obrigatórias."
    )

with st.container(border=True):
    st.subheader("Upload de Arquivos")
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos CSV", 
        type=["csv"], 
        label_visibility="collapsed", 
        accept_multiple_files=True
    )

    if uploaded_files:
        if st.button("Processar Arquivos", type="primary"):
            bar_progress = st.progress(0, text="Iniciando análise...")
            
            for i, arquivo in enumerate(uploaded_files):
                bar_progress.progress((i + 1) / len(uploaded_files), text=f"Validando {arquivo.name}...")
                
                try:
                    session = FileSession(arquivo, len(st.session_state["fila_arquivos"]) + i)
                    session.timestamp_upload = time.time()
                    session.processar()
                    st.session_state["fila_arquivos"].append(session)
                    
                except Exception as e:
                    st.error(f"Erro ao processar {arquivo.name}: {e}")
            
            bar_progress.empty()
            st.rerun()

if st.session_state["fila_arquivos"]:    
    st.markdown("###")
    
    total = len(st.session_state["fila_arquivos"])
    pendentes = len([f for f in st.session_state["fila_arquivos"] if "PENDENTE" in f.status])
    prontos = total - pendentes
    
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Arquivos na Fila", total)
        c2.metric("Processados", prontos)
        c3.metric("Pendentes", pendentes)

    st.subheader("Fila de Processamento")
    
    with st.container(border=True):
        h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
        h1.markdown("**Nome do Arquivo**")
        h2.markdown("**Status**")
        h3.markdown("**Resumo**")
        h4.markdown("**Ação**")
        
        st.divider()
        
        for idx, item in enumerate(st.session_state["fila_arquivos"]):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1], vertical_alignment="center")
            
            c1.markdown(f"{item.nome}")
            
            if item.status == "PRONTO_VALIDO":
                c2.markdown(":green[Válido]")
            elif "PRONTO" in item.status:
                c2.markdown(":blue[Corrigido]")
            elif item.status == "FALHA_MANUAL":
                c2.markdown(":red[Falha Ignorada]")
            else:
                c2.markdown(":orange[Requer Atenção]")
                
            if item.validacao["valido"]:
                c3.caption("Sem erros")
            else:
                c3.markdown(f":red[{item.validacao['total_erros']} erros]")
                
            with c4.popover("Opções"):
                st.caption(f"Arquivo: {item.nome}")
                if st.button("Remover da Fila", key=f"btn_rm_{idx}", type="secondary"):
                    remover_arquivo(idx)
                    st.rerun()
            
            if idx < len(st.session_state["fila_arquivos"]) - 1:
                st.divider()

    st.markdown("###")

    nomes_abas = [item.nome for item in st.session_state["fila_arquivos"]]
    if nomes_abas:
        st.subheader("Detalhamento Técnico")
        abas = st.tabs(nomes_abas)

        for aba, item in zip(abas, st.session_state["fila_arquivos"]):
            with aba:
                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(f"**Linhas:** {item.df_original.shape[0]}")
                m2.markdown(f"**Colunas:** {item.df_original.shape[1]}")
                m3.markdown(f"**Delimitador:** `{item.delimitador}`")
                m4.markdown(f"**Encoding:** `{item.encoding}`")

                with st.expander("Visualizar Dados do Arquivo"):
                    st.dataframe(
                        item.df_original, 
                        width='stretch',
                        height=200
                    )

                if item.validacao["valido"]:
                    st.success("Estrutura e dados validados com sucesso.")
                else:
                    st.error(f"Foram encontradas {item.validacao['total_erros']} inconsistências.")
                    
                    st.markdown("#### Relatório de Divergências")

                    for i, erro in enumerate(item.validacao["detalhes"]):
                        with st.container(border=True):
                            st.markdown(f"**{formatar_titulo_erro(erro.get('tipo'))}**")
                            
                            tipo_erro = erro.get("tipo")
                            if tipo_erro == 'nomes_colunas':
                                mapeamento = erro.get("mapeamento", {})
                                if mapeamento:
                                    df_map = pd.DataFrame(list(mapeamento.items()), columns=["Arquivo", "Esperado"])
                                    st.dataframe(df_map, hide_index=True)
                                else:
                                    st.caption("Mapeamento automático não disponível.")

                            elif tipo_erro == 'formato_valor':
                                formato = erro.get("formato_detectado", "Desconhecido")
                                c_a, c_b = st.columns(2)
                                c_a.markdown(f"Detectado: `{formato}`")
                                c_b.markdown("Esperado: `Decimal`")

                            elif tipo_erro == 'formato_data':
                                formato = erro.get("formato_detectado", "Desconhecido")
                                c_a, c_b = st.columns(2)
                                c_a.markdown(f"Detectado: `{formato}`")
                                c_b.markdown("Esperado: `YYYY-MM-DD`")

                            elif tipo_erro == 'colunas_faltando':
                                colunas = erro.get("colunas", [])
                                st.markdown(f"Colunas ausentes: `{', '.join(colunas)}`")

                            elif tipo_erro == 'colunas_duplicadas':
                                conflitos = erro.get("conflitos", {})                                
                                dados_conflito = [
                                    {"Campo Esperado (Destino)": dest, "Colunas no Arquivo (Origem)": ", ".join(origs)}
                                    for dest, origs in conflitos.items()
                                ]
                                df_conflito = pd.DataFrame(dados_conflito)
                                st.dataframe(
                                    df_conflito, 
                                    hide_index=True,
                                    width='stretch',
                                    column_config={
                                        "Campo Esperado (Destino)": st.column_config.TextColumn("Campo Final", width="medium"),
                                        "Colunas no Arquivo (Origem)": st.column_config.TextColumn("Colunas Conflitantes", width="large"),
                                    }
                                )
                            else:
                                st.write(erro)

    st.divider()

    col_vazio, col_acao = st.columns([3, 1])
    
    with col_acao:
        if pendentes > 0:
            if st.button("Iniciar Correção", type="primary", width='stretch'):
                st.session_state["indice_atual"] = 0
                st.switch_page("pages/2_Correção_IA.py")
        
        elif total > 0:
            if st.button("Avançar para Inserção", type="primary", width='stretch'):
                st.switch_page("pages/3_Inserção_Banco.py")